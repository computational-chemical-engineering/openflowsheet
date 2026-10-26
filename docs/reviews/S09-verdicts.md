# S09 — verdicts on evidence (BioSTEAM as a third column reference, X31's three-tool reference clause, D19's three-tool statement)

**Lane:** design (`verdict`), work order WO-S09-4 (spec §12, as amended by §18.6). **Date:** 2026-10-26.
**Branch:** `wp/S09` at `293cb19b`. The qualification commit is `95643b4c`. The comparison commit is `94a9d0c0`:
`benchmarks/s09/references/comparison.json`, SHA-256 `3feb65e5de6482fe508bb9c6035260f7b3a68a825e2ab2642edc1db2da186423`. Its
manifest is `evidence/S09/6ce5b624bc9e1c27c6d256e67faa175a56991075/manifest.json`: `implemented`, 25 of 28 checks pass. A19 fails
because this document did not exist; `S09.gate` and `S09.ci` are `unsupported`. **Authority:** `docs/derivations/S09-spec.md`
(SHA-256 `e9c25fe7…330a`): §2.3, §6–§9 and §14, as amended by Amendment 1 (§18). It composes with `docs/derivations/S03-spec.md`
§6, §7.1, §17.3–§17.5. The form follows `docs/reviews/S03-verdicts.md`.

**Standing.** These are agent verdicts, numerical and procedural. They are not scientific review. `review.numerical` and
`review.process_model` stay `pending` for Frank's sign-off, and nothing here claims them. This document does not set `reviewed`. It
does not replace the package's single `reviewer` pass (§12), which is running concurrently and has not reported. No tool was run.
§0 lists what was run.

## The verdicts

| # | Criterion (as registered) | Verdict |
| --- | --- | --- |
| 1 | Classification of every (case, BioSTEAM) pair: S03 §7.1's order, with S09 §6.2–§6.5 (B2 as restated by §18.3) and the L2(c) rerun of §18.4(b), on the committed records (19 pairs, plus 2 registered absences) | **Confirmed as recorded.** 17 `AGREE`. 2 `DISAGREE`, both controls, as required. No `NOT_COMPARABLE` of any kind, no genuine `DISAGREE`. (PC-L, BioSTEAM) and (PC-LI, BioSTEAM) `not_applicable`. An independent recomputation from the records' raw fields gives the same label for 19 of 19 pairs, the same worst quantity, the same worst ratio and the same count outside (§0) |
| 2 | Positive controls: §7 with S03 §17.3 | **MET.** (PC-LB, BioSTEAM) is `DISAGREE`: maximum 243.292 tolerances (`Q_reboiler`), 22 of 29 outside, which is the registered discrimination. It lands within 3.55e-7 of a tolerance of its tool-model twin (PC-LI's). (PC-P, BioSTEAM) is `DISAGREE`: 175.914 (`T[1]`), 28 of 29 outside; its tool-model distance is `not_applicable(tool_model_differs)`, as registered. No control is `AGREE`. BioSTEAM's pairs count |
| 3 | X31's reference clause, three-tool form: §8.1's table and §8.2's clause (RC1–RC4) | **MET WHERE AVAILABLE, 3 of 4** (target 4). RC1 and RC2: row 5, three references. RC3: row 5, two references (BioSTEAM, IDAES). RC4: row 6, one reference (BioSTEAM; DWSIM and IDAES absent). This is §8.3's pre-registered best reachable outcome. "Met with two references" is not met, and was unreachable |
| 4 | Inverse kinds, per §8.2's last line, outside the count | **All three kinds have at least two references.** Purity (RC5): row 5, three. Recovery (RC6): row 5, three. Temperature (RC7): row 5, two (BioSTEAM, IDAES) |
| 5 | D19, three-tool statement (§8.4): per registered state, how many independent implementations agree, with tool, level and the disclosure of §2.1 and §9 | **Stated (§5).** Three implementations at 9 states, two at 5, one at 3 (the RC4 family, BioSTEAM at L2(c) only), none at 0. The disclosure, with §9.1 quoted, is §5.2. Numerical verification, not validation |
| 6 | Perturbation study (S03 §7.4, A18): reported, not classified | **Reported.** BioSTEAM compares all 10 perturbed cases, RC4-D and RC4-z included, which neither S03 tool compared. Each BioSTEAM finite-difference response matches ours to within 9.0e-4 of its bound, while the twin's response is at least 4209 bounds |
| 7 | A19 (§11): this document exists, is the `verdict` agent's, and records §8's items and §9.1's disclosure | **Met once this file is committed.** The manifest at `6ce5b624` still records A19 as failed. Regenerating it is the build lane's task |

Status lines. None of these is a verdict item, and none changes a verdict above.

| Item | Status |
| --- | --- |
| The `reviewer` pass over WO-S09-1 to WO-S09-3 (harness against §5 and §6, the read-back, the L2(c) loop) | Pending. If it finds a harness defect, verdicts 1, 3, 4 and 5 reopen for the affected pairs (§1.5) |
| `scripts/gate.sh`, and CI green on both architectures (§13) | Not run. The manifest marks both `unsupported`. Both are required before the merge |
| Ledger rows X31 and D19 (§8.5) | The build lane fills them from this document after it is committed. Status moves only as this verdict and the release gate allow |
| Q-S09-2 (ChemSep if BioSTEAM cannot model RC4) | BioSTEAM qualified RC4. Under Q-S09-2's default, nothing is queued |
| Q-S09-4 (is PC-P the only `DISAGREE` control?) | Settled: no. PC-LB is `DISAGREE`, so no BioSTEAM-specific PC-P tool model is needed |
| WO-S09-1's open item (hash numpoly's compiled extension in the fingerprint) | Not ruled here. It moves no classification: every record's pip-freeze fingerprint equals §9's |

---

## 0. The evidence judged, and its provenance

These verdicts apply to the bytes below. They do not transfer to other records.

| Record | Produced by, where | SHA-256 |
| --- | --- | --- |
| BioSTEAM: 19 records `results/biosteam-<case>.json` and `qualification/biosteam.json` | WO-S09-2's second attempt (a fresh build-lane agent), harness at `fd38124d` (clean at head, recorded in `harness`), `.venv-biosteam` (BioSTEAM 2.54.0, thermosteam 0.54.2, CPython 3.13.5). Committed in `95643b4c` | each listed in `SHA256SUMS`; `qualification/biosteam.json` `cb8b9289…0f72` |
| Our side: S03's 18 `ours-*.json`, unchanged; PC-LB aliases RC1 | S03, pinned through `cmp3` | listed in `cmp9 → inputs_sha256` |
| Cases and twin | `s03_cases.json`, `s03_reference.json`, `s09_cases.json` (181 claims, `--check` passing in the manifest) | `c901d6c9…3f39`; `95ef9bd2…0c67`; `760ab27f…a813c` |
| IDAES and DWSIM classes | S03's `comparison.json`, read, never re-classified | `5c7d139c…585d` |
| Comparison | `scripts/s09_reference_comparison.py --write` at `94a9d0c0` | `comparison.json` `3feb65e5…6423`; `SHA256SUMS` `83a68526…1572` |

**What I checked, and how.**
- **Hashes.** All 21 entries of `SHA256SUMS` (19 records, the qualification file, `comparison.json`) match the files at `293cb19b`.
  The three S03 pins and `s09_cases.json` equal the hashes S09 §0 and §18 register.
- **Order (§2.3 step 3, A16).** `git merge-base --is-ancestor 95643b4c 94a9d0c0` succeeds. `95643b4c` is the only commit that touches
  `qualification/` or `results/`. The classifier `scripts/s09_reference_comparison.py` first appears in `94a9d0c0`. Between
  `fd38124d` and `293cb19b`, `git diff` touches no file under `spikes/references/`, and neither `S09-spec.md` nor
  `docs/derivations/scripts/` changes after `95643b4c`. The records judged are the records the harness wrote.
- **Fingerprints.** All 19 records carry pip-freeze SHA-256 `0edea300…9a95`, equal to `docs/reference-environments.md` §9. No pair is
  rule 1.
- **Repeat run (A17).** `qualification/biosteam.json → repeat_run.all_identical` is true for all 19 cases (the second run is outside
  the repository; the block carries both runs' hashes). I did not re-run the tool.
- **Independent recomputation.** I wrote a scratch script that imports nothing from the repository and kept it out of the commit. The
  SYN-001 constants are typed in from T06's values (`spikes/references/t06_fixtures.py:36–43`). For each record it reads the **selected rung's raw profile** (per-stage T, P, L, V, x, y,
  inlet and outlet component flows, duties; inlets and products), not the harness's summaries, and:
  - rebuilds the registered quantities from the profile by S03 §4 (a total condenser's reflux as stage 0's liquid minus the side
    draw). They equal the recorded `quantities` and `registered_quantities` bit for bit in 19 of 19 records;
  - recomputes B1, B2 (with §18.3's counter on R3), B3, B4 (K from SYN-001's closed form at the stage's T and P), B5, the pressures,
    the intermediate duties, the total-condenser vapour, every specification by S03 §5.1 row 9 and §17.4, rule 2d's specification
    residual per kind, the rerun movement and the path spread in the twin's tolerance, rule 3 and rule 4, with §6's tolerance in
    50-digit decimal from the twin's 25-digit strings;
  - recomputes rule 2 on every recorded rung of every attempted level. It agrees with the harness's pass or fail on each, and the
    selected rung is the first passing one in §5.3's order in 19 of 19;
  - checks every stored specification after pass 2 against §5.6's conversion in binary64 (`1/RR`, `BR`, `B/F`, `3.6 Q`, side draw
    `1/(1+RR)`, and at L2(c) `1/x` or `x`): equal in 19 of 19. The inlet stages equal the registered ones. The accuracy rerun's x
    equals the run's final x in all seven L2(c) records;
  - recomputes each tool `Psat` read-back value from the closed form: equal bit for bit, in every record. PC-LB's record carries
    `Hvap` 25010, 30010 and 35010 J/mol, §7's values;
  - applies §17.3 and §8.1's table, and S03 §17.5's table to the two S03 tools alone.

  *Result.* The same label for 19 of 19 pairs; the same worst quantity and ratio (to the digits printed in §1.2) and the same count
  outside; the same rows and clause; and the two-tool reduction gives S03's committed rows (5, 5, 6, 7) and "not met".
  *What it does not check.* It takes the structural inspections (Q-X1 to Q-X10) and the tool's enthalpies as recorded. B5's energy
  closure uses the recorded `H_W` and duties. For the seven L2(c) records I checked that the L1 inspection recorded the
  specification inexpressible and L1 was not attempted (A08's precondition).
- **Re-runs of committed checks** (read-only): `scripts/s09_reference_comparison.py --check` exit 0;
  `pytest tests/test_s09_qualification.py tests/test_s09_environment.py`: 13 passed (A03 at head and at the qualification commit, A04's
  file part, A06–A08). I did not re-run `tests/test_s09_references.py`; the manifest records 125 passed.

**Provenance notes.** None moves a classification.
- **N1 (development runs, Amendment 1's timing).** WO-S09-2's first attempt made four development runs, dev0–dev3, with the PCF class
  string replaced in memory. Their outputs were not committed, so I cannot verify them; the build log is the only account. They read
  only the tool's own residuals; no comparison existed. Amendment 1 was ruled after them and before the recorded run. On the build
  log's account the amendment selected nothing:
  - dev1 found all 19 cases available at the same levels and rungs as the recorded run;
  - §18.4(b) changed the L2(c) rerun. Under the original form dev1's RC6 and RC7 reruns moved 0.026 and 0.020 tolerance, inside rule
    2d's 0.1, so the change moved only a thin-margin flag, which is a disclosure (§18.4(a));
  - §18.3 tightens R3 only, and R3 fails rule 2 on all 19 cases in the recorded run.

  So the amendment is post hoc with respect to tool-internal outcomes, not with respect to any comparison, and it is disclosed (§5.2).
- **N2 (B4's K).** §6.2 registers B4 with K from the tool's `Psat` object. The classifier (build decision, WO-S09-3) and my script use
  SYN-001's closed form. They are equivalent here: the tool's read-back `Psat` equals the closed form bit for bit at the four
  registered temperatures, and the build lane measured ≤ 1.2e-15 against the harness's per-stage tool K, against a 1e-8 threshold.
- **N3 (build log figure).** `docs/S09_BUILD_DECISIONS.md` (WO-S09-3, B5 decision) says "intermediate duties ≤ 2.6e-8 W". The records
  carry up to 1.06e-7 W (RC4; RC3 family 2.6e-8 to 7.9e-8 W). The threshold is 1e-3 W, so nothing depends on it. The log should be
  corrected.
- **N4 (a forbidden string in a record, by construction).** §9.2 forbids `1.2341901` (the twin's RC4 reflux ratio) in the tool
  scripts. It appears in `results/biosteam-RC4.json` as the L2(c) loop's returned x, `1.234190189274101`. That is output, not input:
  A03 scans the scripts, and passes; the loop started at 1 and 2 and bracketed on [1, 2]; the twin's value is
  `1.234190189266853…`, 5.9e-12 relative away, which is what C5 predicts when the specification D = V₁ = 0.5 is met to |g| = 4.4e-12.
  A future blindness scanner extended to records would flag it falsely.
- **N5.** The WO-S09-2 agent took S03's allowances from `s03_qualify_dwsim.py`'s constants. They enter only the harness's own rerun
  and path ratios, which the classifier recomputes in the twin's tolerance (differences ≤ 2.1e-4 relative). No effect.

## 1. Verdict 1: the pair classifications

### 1.1 Criteria as registered

- *Tolerance.* S03 §6: `|ours − tool| ≤ a_k + 1e-6 |v_twin|`, with a_flow 3.1e-7 mol/s, a_T 1e-5 K, a_duty 1e-2 W, unrounded, no
  per-case or per-tool factor (§6.5).
- *Rule order.* S03 §7.1: rules 0, 1, 2, 2c, 2d, 3, 4 (2b is IDAES only).
  - Rule 2 is §6.2's B1–B5; B2 reads `iter` on R1, R2, R4 and fsolve's `nfev` on R3, which must have run (§18.3).
  - Rule 2c is S03's, plus the specification read-back, the total-condenser vapour and the property read-back (§6.3).
  - Rule 2d is S03 §17.4's specification residual per kind, the accuracy rerun (§18.4(b): at L2(c) one evaluation at the final x),
    and path dependence among passing rungs (§6.4). It can only exclude.
- *Selection.* The first rung passing rules 2–2d in §5.3's order, at the first level that passes (§2.3 step 1).
- *Thin margin.* A disclosure; it moves no classification (§18.4(a)).
- *Limits on this verdict.* The `verdict` agent may not change a tolerance, a setting, a mapping, a level or a case (S03 §7.5, §12 rule 3).

### 1.2 Per case

Rungs: R1 inside-out, R2 phenomena, R3 simultaneous correction (fsolve), R4 sequential modular (§5.3). Ratios are in tolerances.

| Case | Classification | Level, rung, outer evaluations | Worst quantity (ratio), outside | Tool vs twin | Rerun movement | Path spread (rungs) |
| --- | --- | --- | --- | --- | --- | --- |
| RC1 | **AGREE** | L1, R1 | `bottom[A]` 1.50e-6, 0/29 | 3.6e-7 | 1.2e-6 | 1.05e-4 (R1, R2, R4) |
| RC2 | **AGREE** | L1, R1 | `L[2]` 1.54e-6, 0/28 | 1.5e-6 | 2.5e-6 | 9.2e-5 (R1, R2, R4) |
| RC3 | **AGREE** | L1, R2 | `bottom[B]` 3.51e-3, 0/21 | 4.2e-6 | 3.4e-5 | 7.6e-5 (R2, R4) |
| RC4 | **AGREE** | L2(c), R2, 7 | `L[2]` 1.02e-5, 0/22 | 1.0e-5 | 3.8e-5 | 7.2e-5 (R2, R4) |
| RC5 | **AGREE** | L2(c), R1, 9 | `L[3]` 5.1e-7, 0/29 | 5.0e-7 | 7.3e-7 | 1.54e-4 (R1, R2, R4) |
| RC6 | **AGREE** | L2(c), R1, 7 | `bottom[A]` 0.0202, 0/28 | 1.7e-6 | 7.4e-7 | 1.17e-3 (R1, R2, R4) |
| RC7 | **AGREE** | L2(c), R1, 9 | `top[B]` 1.14e-6, 0/29 | 7.9e-7 | 1.1e-6 | 6.0e-5 (R1, R2, R4) |
| RC1-RR | **AGREE** | L1, R1 | `bottom[A]` 1.75e-6, 0/29 | 3.7e-7 | 1.6e-6 | 1.05e-4 |
| RC1-BR | **AGREE** | L1, R1 | `bottom[A]` 1.58e-6, 0/29 | 3.6e-7 | 1.2e-6 | 1.22e-4 |
| RC1-z | **AGREE** | L1, R1 | `bottom[A]` 2.65e-7, 0/29 | 1.9e-7 | 5.7e-7 | 1.12e-4 |
| RC2-RR | **AGREE** | L1, R1 | `L[2]` 1.56e-6, 0/28 | 1.6e-6 | 2.5e-6 | 1.10e-4 |
| RC2-B | **AGREE** | L1, R1 | `L[2]` 1.39e-6, 0/28 | 1.4e-6 | 2.8e-6 | 9.8e-5 |
| RC2-z | **AGREE** | L1, R1 | `L[3]` 1.37e-6, 0/28 | 1.4e-6 | 1.3e-6 | 9.1e-5 |
| RC3-Q | **AGREE** | L1, R2 | `bottom[B]` 2.35e-3, 0/21 | 1.5e-6 | 2.4e-5 | 8.2e-5 (R2, R4) |
| RC3-z | **AGREE** | L1, R2 | `bottom[B]` 1.70e-3, 0/21 | 4.6e-6 | 4.1e-5 | 7.1e-5 (R2, R4) |
| RC4-D | **AGREE** | L2(c), R2, 7 | `L[2]` 5.96e-6, 0/22 | 6.4e-6 | 2.3e-4 | 8.2e-5 (R2, R4) |
| RC4-z | **AGREE** | L2(c), R2, 7 | `L[3]` 4.59e-6, 0/22 | 4.6e-6 | 6.4e-5 | 8.3e-5 (R2, R4) |
| PC-P | **DISAGREE** (required) | L1, R1 | `T[1]` 175.914, 28/29 | — | 2.7e-6 | 1.17e-4 |
| PC-LB | **DISAGREE** (required) | L1, R1 | `Q_reboiler` 243.292, 22/29 | — | 1.2e-6 | 1.05e-4 |
| PC-L, PC-LI | `not_applicable` (registered absences, no record) | — | — | — | — | — |

Every level and realization is §2.5's expected one. Q-S09-1's answer: every case qualified, every L2(c) loop found a bracket ([1, 2]
for the RC4 family and RC6; [2, 4] after one step up for RC5 and RC7).

**Reason for every `AGREE`.** Rules 0 to 3 do not fire, and every registered quantity lies within §6's tolerance.
- *Rule 2* (largest over the 17 selected records): B3 2.2e-12 mol/s (RC4) against 3.1e-8; B4 6.5e-12 (RC4) against 1e-8; B5 component
  2.2e-12 mol/s, energy 1.5e-11 W against 1e-3 W. No exception, no capped iteration, no one-phase stage.
- *Rule 2c.* Stage counts, maps and inlet stages match. Every pressure deviation is 0 Pa. Intermediate duties ≤ 1.06e-7 W (RC4) against 1e-3. The
  total-condenser vapour is exactly 0 on the RC2 family and RC6. Every stored specification reads back exactly. Every property
  read-back passes. The largest relative miss of a specification definition is 6.4e-12, against 1e-4.
- *Rule 2d.* Specification residuals ≤ 6.4e-4 of their kind's threshold (RC3-z; at L2(c) ≤ 4.4e-4, RC4). Rerun movement ≤ 2.3e-4
  tolerance (RC4-D). Path spread ≤ 1.17e-3 (RC6).
- *L2(c) (C4, A08).* Every outer evaluation passed the inner checks; every final |g| is within ytol (largest 4.4e-12 against 1e-9,
  RC4); every rerun is one evaluation at the binary64 final x.
- *Rule 3.* Our side is within 0.0202 of a tolerance of the twin on every case (RC6 `bottom[A]`) and within 3.5e-3 on every other.

**The third corner.** In every `AGREE` pair BioSTEAM lies within 1.02e-5 of a tolerance of the twin (RC4 `L[2]`). Every worst
comparison ratio above that, RC6's 0.0202 and the RC3 family's 1.7e-3 to 3.5e-3, is our side's own distance from the twin, which S03
recorded and rule 3 admits. Ours, the tool and the twin agree pairwise; no `AGREE` rests on two corners alone.

**Margin, reported, not used.** The largest margin-row ratio (§18.4(c)) of any selected record is 0.0117 (RC6, path spread); the
next is 2.3e-3 (RC4-D, rerun movement). The thin-margin list is empty. Unlike DWSIM's RC1 family in S03, no BioSTEAM record sits near
an accuracy floor.

**Rung outcomes (facts about this tool and harness, §14).** R3 fails rule 2 on all 19 cases. R1 fails B3 on the RC3 and RC4
families. So path dependence compares three rungs (R1, R2, R4) on 13 records and two (R2, R4) on the RC3 and RC4 families.

### 1.3 The rulings that set the tool path: when each was fixed, and whether it is tuning

No comparison existed before `94a9d0c0`.

| Ruling | Fixed | Tuning? |
| --- | --- | --- |
| Levels L1 and L2(c), the ladder (the tool's default chain, all four rungs run), settings, two-pass path, outer loop (§2, §5; R-741, R-743) | The specification, before any qualification run | **Not tuning.** Uniform and closed. The ladder is the tool's documented default; the starts 1 and 2 are generic. For a monotone residual, §5.4's expansion brackets any root in [1/16, 32], so there the starts change the number of evaluations, not availability |
| Amendment 1 (R-748 to R-750) | After dev0–dev3 (tool-only), before the recorded run and before any comparison | **Not tuning; post hoc with respect to tool-internal outcomes, and disclosed** (N1). Two errata, a B2 restatement that tightens R3 only, and an L2(c) rerun form. On the build log's account none of them changed a case's availability, level or rung |
| PC-LB (§7, R-745) | The specification, before any run | **Not chosen by convergence.** Its configuration and size are PC-LI's, registered in S03 before BioSTEAM. It reproduces its registered discrimination (243.292) and its tool model to 3.55e-7 |

### 1.4 Alternatives rejected

- **Discount the L2(c) `AGREE`s because the specification equation is the harness's.** Rejected. L2(c) was admitted under C1–C6
  before any run. C4 is met on every record, and by C5 a loop that found another root would `DISAGREE`, never `AGREE`. What an L2(c)
  `AGREE` verifies is narrower than an L1 one, and §5 and §8 say so; that limits the claim, not the classification.
- **Treat the spike's exposure as tainting RC4.** Rejected. The recorded harness was written from the specification by a fresh agent,
  A03 passes at head and at the qualification commit, the starts are generic, and RC4's answer is fixed by D = 0.5 (C5, N4). What an
  exposed author could still influence is availability (§9.3); for a monotone residual the registered bracket rule reaches any root in
  [1/16, 32], so a root at 1.234 gained nothing that a root elsewhere in that range would lack.
- **Require a control on each harness route** (L2(c), total condenser, no condenser, no reboiler). Rejected under the registered
  criterion: S03 §17.3 makes controls per tool, and its point 2 considered exactly this. Recorded as a limitation (§2, §8 item 4).
- **Re-judge IDAES or DWSIM pairs.** Rejected: S09 §0 and §8.1. Their classes are read from S03's pinned `comparison.json`.
- **A tighter verdict tolerance "because the margins allow it".** Rejected. The `verdict` agent may not change a tolerance.
- **Withhold the verdict until the reviewer reports.** Rejected. The plan orders WO-S09-4 beside the review; §1.5 names what reopens
  if the reviewer finds a defect.

### 1.5 What would change it

- The `reviewer` finds a harness defect against §5 or §6: the read-back, the B2 counter, the L2(c) loop or its rerun form, or a
  realization other than the registered one. Rule 6 then requires correcting the harness, repeating the run and a new verdict for the
  affected pairs.
- A tool script shown to have read our results, the twin or a comparison output (A03).
- A re-run of `spikes/references/s09_qualify.sh` that does not reproduce the committed records, or a fingerprint mismatch.
- CI's re-classification on the second architecture changing a label or a §8.1 row, not only last bits.
- A change of SYN-001's definition, BioSTEAM's mapping, the tool version, a setting or a tolerance. Each requires re-qualification and a
  new verdict.

## 2. Verdict 2: the positive controls

**Criteria as registered** (§7, S03 §17.3): (a) a control classified `AGREE` stops the comparison; (b) BioSTEAM's pairs count only if
PC-LB or PC-P classifies `DISAGREE`; (c) a `NOT_COMPARABLE` control propagates nothing; (d) (PC-L, BioSTEAM) and (PC-LI, BioSTEAM) are
`not_applicable`.

| Control | Classification | Max ratio (quantity), outside | Registered discrimination | Distance to the tool-model twin |
| --- | --- | --- | --- | --- |
| (PC-LB, BioSTEAM) | `DISAGREE` | 243.292 (`Q_reboiler`), 22/29 | 243.292, 22/29 | 3.55e-7 (`L[2]`), against `ref.controls.PC-LI.tool_model` |
| (PC-P, BioSTEAM) | `DISAGREE` | 175.914 (`T[1]`), 28/29 | S03's 176.357 is for a tool model without the Poynting factor alone | `not_applicable(tool_model_differs)` |
| (PC-L, BioSTEAM), (PC-LI, BioSTEAM) | `not_applicable` | — | — | — |

- **PC-LB comes from the effect it exists to show.** Its distance to PC-LI's tool model is 3.55e-7 of a tolerance, so the
  `DISAGREE` is the 10 J/mol `P_r v_i` in the latent heat, resolved by the harness.
- **The marginal quantities are as registered.** PC-LB's `T[4]`–`T[7]` sit at 0.585–0.782 of a tolerance (§7: 0.585–0.782); `T[1]`–`T[3]`
  at 1.51–2.08. The duties and flows carry it.
- **PC-P.** 28 of 29 quantities are outside; `bottom[C]` is inside at 0.515. BioSTEAM lacks both the Poynting factor and the liquid
  `v (P − P_r)` term, so its tool model is not S03's, and no distance is computed. I make no claim about which missing term produces
  the 0.44-tolerance difference from 176.357.

**What the controls do not show.**
- *Both controls cover one harness route*: RC1's configuration (partial condenser, kettle reboiler) at (L1, R1). No control ran on
  the total-condenser route (RC2 family, RC6), on the no-condenser route at R2 (RC3 family), on the no-reboiler route (RC4 family) or
  on any L2(c) loop (RC4 family, RC5–RC7).
  - The registered criterion accepts this (S03 §17.3 point 2).
  - What guards those routes is rule 2c's per-record checks, A03, and the perturbation discriminations. On the RC4 family, where
    BioSTEAM is the only reference, its response to a 2 % change of D matches ours to 2.4e-6 of the bound while the twin moves 8111
    bounds (RC4-D), and to 7.0e-6 against 14048 for the feed change (RC4-z). That is corroboration that the harness reads the tool's
    answer on that route, not a registered control.
- *The missing Poynting terms.* PC-P shows the combined effect of BioSTEAM's two missing terms, not either one. Our Poynting terms stay
  without an independent check (§14).

## 3. Verdict 3: X31's reference clause, three-tool form

**Criteria as registered** (§8.1–§8.3): the count covers RC1–RC4. IDAES's and DWSIM's classes are read from S03's pinned
`comparison.json`; BioSTEAM's from S09's. The first matching row of §8.1 decides each case. §8.3 pre-registers the outcomes.

| Case | DWSIM | IDAES | BioSTEAM | §8.1 row | Outcome |
| --- | --- | --- | --- | --- | --- |
| RC1 | comparable, `AGREE` | comparable, `AGREE` | comparable, `AGREE` (L1, R1) | 5 | three references |
| RC2 | comparable, `AGREE` | comparable, `AGREE` | comparable, `AGREE` (L1, R1) | 5 | three references |
| RC3 | absent | comparable, `AGREE` (L3, P1) | comparable, `AGREE` (L1, R2) | 5 | two references (BioSTEAM, IDAES) |
| RC4 | absent | absent | comparable, `AGREE` (L2(c), R2) | 6 | one reference (BioSTEAM) |
| **X31 reference clause** | | | | | **met where available: 3 of 4 cases at row 5 (target 4)** |

**The absent tools and their reasons** (row 6 requires them quoted; they are S03's, `docs/reviews/S03-verdicts.md` §3):
- *RC3, DWSIM.* L1 Napthali–Sandholm: no tolerance passed rules 2–2d (iteration limit). L1 Wang–Henke: DWSIM's own mass-balance
  check failed at 1e-10 to 1e-8, and rule 2's balance at 1e-7 and 1e-6. L3: not admissible for DWSIM.
- *RC4, DWSIM.* L1: a full-reflux condenser has no native vapour-distillate rate (D = V₁) under either method. L2(a): a DWSIM error
  (Napthali–Sandholm) and a convergence error (Wang–Henke). L3: not admissible.
- *RC4, IDAES.* L1 and L2: `TrayColumn` always builds a kettle reboiler, so RC4's `none` reboiler end is inexpressible. L3: P0, P1 and
  P2 each ended at 500 iterations.

**Against the pre-registration.**
- §8.3: BioSTEAM `AGREE` on all four counted cases gives rows 5, 5, 5, 6 and "met where available, 3 of 4", the best reachable
  outcome. That is what occurred.
- "Met with two references" requires RC4 at row 5. RC4 can have at most one reference, so it was unreachable, and it is not met.
- *Reduction (claim C9, A15).* With BioSTEAM omitted, the table gives S03's committed rows (5, 5, 6, 7) and S03's clause, "not met".
  I recomputed this independently. The generalization changed nothing S03 decided.
- **S03's verdict stands as S03's record** (§8.5): its two-tool outcome, "not met, 2 of 4", is unchanged. This is S09's three-tool
  outcome under R-746.
- **Whether a release accepts "met where available" is outside S09** (§8.5, §14). This verdict does not say it is enough.

**Alternatives rejected.**
- **Report the clause as "met".** Rejected. §8.2 registers "met with two references" and "met where available" as distinct outcomes;
  the second carries its count.
- **Count the twin as a second reference for RC4.** Rejected. It shares SYN-001's closed forms and S02's definitions with our
  implementation, so it is not independent (S03 §2.1).
- **Re-qualify DWSIM or IDAES on RC4 to reach row 5.** Rejected: S09 adds a tool and re-judges neither (§0), and S03 §18.1 and §17.2
  closed those routes.

**What would change it.**
- A harness defect in BioSTEAM's RC4 build or loop found by the reviewer: after correction RC4 could be row 7 (absent), and the clause
  "not met"; or row 2 on a genuine `DISAGREE`, and "not met".
- The same for RC3: RC3 would return to row 6, and the clause would read "met where available, 2 of 4".
- Both BioSTEAM controls failing to `DISAGREE` on a re-run: every counted case row 4, and the clause "not met" (§8.3).
- A second independent reference for RC4, by a later package under its own registered rule: only then could the clause reach "met with
  two references".

## 4. Verdict 4: the inverse kinds (outside the count)

| Kind | Case | DWSIM | IDAES | BioSTEAM | Row | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| purity | RC5 | `AGREE`, (L1, Napthali–Sandholm, 1e-10) | `AGREE`, (L3, P1) | `AGREE`, (L2(c), R1, 9) | 5 | three references |
| recovery | RC6 | `AGREE`, (L1, Napthali–Sandholm, 1e-10) | `AGREE`, (L2, P1) | `AGREE`, (L2(c), R1, 7) | 5 | three references |
| temperature | RC7 | absent (structural: DWSIM's temperature specification is stage 7's) | `AGREE`, (L3, P0) | `AGREE`, (L2(c), R1, 9) | 5 | two references (BioSTEAM, IDAES) |

- **BioSTEAM's loops.** RC5: `Reflux` on stage 0 adjusted until the purity of A in `v_1` is 0.85; final g 6.1e-15 (ytol 1e-9). RC6:
  `Boilup` on stage 6 adjusted until the recovery of C in `l_7` is 0.99; final g −3.3e-15 (ytol 1e-10). RC7: `Boilup` adjusted until
  our stage 6 (index 5) is at 368 K; final g 5.3e-15 relative (ytol 1e-10), and stage 6 stays adiabatic (intermediate duties ≤ 1.4e-9 W).
- **How each reference realizes the specification.** DWSIM's RC5 and RC6 are native tool features. IDAES's RC5–RC7 are equations
  written by the harness (L2(b)/L3). BioSTEAM's RC5–RC7 are the harness's outer loop. So **the temperature kind has two references,
  and in both the specification equation is the harness's**; no tool's native temperature specification is exercised.
- **RC6 stays the most ill-conditioned state** (σ_min 6.06e-4). BioSTEAM lands within 1.7e-6 of a tolerance of the twin there; our side
  is the least accurate of the four corners (0.0202), inside rule 3 by a factor of 5, as S03 recorded.

## 5. Verdict 5: D19, three-tool statement

### 5.1 Matched-model inputs

Each record carries the Q-X1–Q-X10 inspection; rule 2c re-checks it on the solved state (§1.2).

| Cases | BioSTEAM realization (BioSTEAM stage indices) |
| --- | --- |
| RC1, RC1-RR, RC1-BR, RC1-z, PC-P, PC-LB | L1: stage 0 `('Reflux', RR*)` (stored `B = 1/RR*`), stage 6 `('Boilup', BR*)` |
| RC2, RC2-RR, RC2-B, RC2-z | L1: stage 0 `('Reflux', inf)` with `bottom_side_draws={0: 1/(1+RR*)}`; stage 6 `('Flow', B*/F)`, F = 1 mol/s |
| RC3, RC3-Q, RC3-z | L1: the `top` inlet on stage 0, which carries no specification; stage 4 `('Duty', 3.6 Q*)` in kJ/h |
| RC4, RC4-D, RC4-z | L2(c): stage 0 `Reflux` adjusted until `V_1 = D*`; no other specification; the vapour `bottom` inlet on stage 4 |
| RC5 | L2(c): stage 0 `Reflux` adjusted until the purity of A in `v_1` is 0.85; stage 6 `('Boilup', 1.5)` |
| RC6 | L2(c): the total condenser at RR 1.5; stage 6 `Boilup` adjusted until the recovery of C in `l_7` is 0.99 |
| RC7 | L2(c): stage 0 `('Reflux', 2)`; stage 6 `Boilup` adjusted until our stage 6 is at 368 K |

**SYN-001 in BioSTEAM** is §4.2's definition: user methods for `Psat`, `Hvap`, `Cn` and `V.l`, the tool's default datum, and
`IdealThermo` with the explicit mixture. §4.3's read-back passes in every record, with the PCF class in the tool's spelling (§18.1).
Every pressure is the registered one exactly (1e5 Pa; 1.5e5 Pa for PC-P).

### 5.2 Independence disclosure

> A comparison verifies a second, independent implementation of the same equations. It is numerical verification, not empirical
> validation. (S03 §2.1, quoted in S09 §2.1)

- **Shared elements.** All five corners — ours, the twin, DWSIM, IDAES and BioSTEAM — share SYN-001's constants, entered in BioSTEAM
  as user input (§4), and the column semantics of S03 §5, matched by construction. An error common to that definition or those
  semantics cannot be seen here.
- **The twin is not independent.** It is the third corner of each pair.
- **BioSTEAM's independence is partial.** No IDAES, Pyomo, DWSIM or Ipopt code is in its stack. It shares numpy and scipy (other
  versions) as its numerical substrate. CoolProp, `thermo` and `chemicals` are in its closure and unused by the registered
  definition (§2.1, §14).
- **Blindness is procedural** (§9.3). A03 passes at head and at the qualification commit. The harness was written by this project's
  build lane, which knows the project, from the specification and the tool's source.
- **The spike's exposure, as §9.1 states it** (quoted, R-747 point 5):

  > - **The spike** (2026-10-25, design-time, scripts and logs in `docs/derivations/scripts/s09_spike/`) chose its solver
  >   settings from the tool's own residuals (`rc3_sweep.py`). By its own account it then compared RC1, RC3 and RC4
  >   informally with this project's committed S03 results (`compare_ours.py`, which read `ours-*.json`). This document
  >   does not repeat those numbers. They are in the brief §4, which the qualification agent must not read (§9.2).
  > - `rc4_sweep.py` and `rc4_respec.py` ran RC4 at the **twin's reflux ratio**, 1.23419018 (S03 §3.1), as their docstrings
  >   say. The re-specification workaround was found at that value.
  > - `rc4_blind.py`'s secant starts (1.0, 1.5) bracket that value. They were chosen by an author who knew it.
  > - **The specifier** read the brief, including §4's summary of that comparison, and S03's twin sanity values, as every
  >   S03 author did. The specifier ran no S03 case and made no comparison. The measurements here (`s09_design/`) are on
  >   non-registered columns and read only the tool's own residuals.

  *How the recorded run stands against it.* The spike's settings were not registered as such (§9.2 point 1); the recorded run was made
  by a fresh agent from a harness written from the specification (points 2 and 3); the registered starts are 1 and 2, not the spike's
  (1.0, 1.5). The registered bracket [1, 2] also contains the twin's RC4 reflux ratio. For a monotone residual §5.4's expansion would have
  reached a root anywhere in [1/16, 32], so that affects the number of evaluations, not availability; and RC4's answer is fixed by
  the specification (C5, N4).
- **Post hoc, disclosed.** Amendment 1 was ruled after four tool-only development runs and before the recorded run (N1). The
  amendment specifier and the second qualification agent record that they opened no comparison, result or twin file.
- **What an L2(c) `AGREE` verifies** (§8.4, §14): our column against BioSTEAM's MESH equations at the state where the harness's outer
  loop meets the specification. The specification equation in that loop is S02's or S06's, written by the harness, not a BioSTEAM
  feature.

### 5.3 The statement, per registered state

| State | Independent implementations that agree | DWSIM | IDAES | BioSTEAM |
| --- | --- | --- | --- | --- |
| RC1, RC1-RR, RC1-z | **3** | L1, Wang–Henke, 1e-8 | L3, P0 | L1, R1 |
| RC2, RC2-B, RC2-z | **3** | L1, Napthali–Sandholm, 1e-10 | L2, P0 | L1, R1 |
| RC2-RR | **3** | L1, Napthali–Sandholm, 1e-10 | L2, P1 | L1, R1 |
| RC5 (purity) | **3** | L1, Napthali–Sandholm, 1e-10 | L3, P1 | L2(c), R1 |
| RC6 (recovery) | **3** | L1, Napthali–Sandholm, 1e-10 | L2, P1 | L2(c), R1 |
| RC1-BR | **2** | absent (rerun 0.1006 > 0.1) | L3, P0 | L1, R1 |
| RC3, RC3-Q, RC3-z | **2** | absent (convergence, §3) | L3, P1 | L1, R2 |
| RC7 (temperature) | **2** | absent (structural) | L3, P0 | L2(c), R1 |
| RC4, RC4-D, RC4-z | **1** | absent | absent | L2(c), R2 |

Totals: three at 9 states, two at 5, one at 3, none at 0. Against S03's two-tool record (two at 9, one at 5, none at 3), every state
gained exactly one reference.

**My answer, within the supported scope** (SYN-001 only, every pressure `P_r`, the registered states):
- **Three independent implementations.** Our column is numerically verified against three for the conventional column — partial or
  total condenser, kettle reboiler, liquid feed — under ratio and rate specifications, and under purity and recovery specifications.
  BioSTEAM's part of the purity and recovery evidence is at L2(c).
- **Two.** For the stripper (no condenser, a liquid `top` inlet, a duty-specified reboiler: IDAES at L3 and BioSTEAM natively at L1);
  for an interior stage's temperature specification (both by a harness-written specification equation); and for one boil-up
  perturbation of the conventional column.
- **One.** For the refluxed absorber (no reboiler, a vapour `bottom` inlet, a vapour distillate rate): BioSTEAM, at L2(c). The column,
  its stages, the `none` reboiler end and the vapour inlet are BioSTEAM's native `MultiStageEquilibrium`; the equation D = V₁ is the
  harness's. S03 recorded this topology as resting on the twin alone. It now has one independent check, through a harness route that no
  control covers (§2).
- **None.** No registered state is without an independent reference.

**D19's minimum evidence for S09's part is present:** matched-model inputs (§5.1), the disclosure (§5.2) and these verdicts. D19 as a
requirement also spans T06 and R01; this covers only the column part, with three tools.

## 6. Verdict 6: the perturbation study (reported, not classified)

The full table is `comparison.json → perturbation_response`, at the SHA-256 in §0. The bound is `tol(y_pert) + tol(y_base)`. My
recomputation:

| Perturbed case | Twin's response: max \|Δy\| / bound | DWSIM (S03) | IDAES (S03) | BioSTEAM: max \|Δy_tool − Δy_ours\| / bound |
| --- | --- | --- | --- | --- |
| RC1-RR | 4209 | 0.0026 | 5.0e-6 | 1.2e-7 |
| RC1-BR | 5183 | — | 1.1e-5 | 5.2e-8 |
| RC1-z | 19432 | 0.0068 | 3.1e-5 | 6.2e-7 |
| RC2-RR | 6806 | 2.6e-9 | 5.2e-6 | 2.2e-8 |
| RC2-B | 10884 | 2.2e-9 | 1.7e-5 | 8.8e-8 |
| RC2-z | 19028 | 1.3e-8 | 2.6e-5 | 3.1e-7 |
| RC3-Q | 16165 | — | 1.3e-3 | 5.9e-4 |
| RC3-z | 16665 | — | 9.0e-4 | 9.0e-4 |
| RC4-D | 8111 | — | — | 2.4e-6 |
| RC4-z | 14048 | — | — | 7.0e-6 |

Where both points are `AGREE`, each response matches ours by construction. The responses cover only registered neighbouring states.
They verify no derivative and are no sensitivity capability (§14).

## 7. What these verdicts do not establish

- **Not empirical validation, not optimality evidence, not a sensitivity capability.** SYN-001 is synthetic. An `AGREE` verifies that
  an independently written implementation of the same equations gives the same root at a registered state.
- **Not BioSTEAM's correctness in general**, nor any claim about its solvers. The rung outcomes (R3 failing everywhere, R1 failing on
  the RC3 and RC4 families) are facts about this tool, these settings and this harness.
- **Not any tool's specification machinery at L2(c).** For the RC4 family and RC5–RC7, BioSTEAM's specification is the harness's loop.
- **Not uniqueness.** Path independence is checked among two or three rungs at one level.
- **Nothing away from `P_r`.** PC-P shows two missing terms combined. Our Poynting terms stay without an independent check.
- **Not that every harness route is guarded by a control.** Both controls are on RC1's L1/R1 route.
- **Not a portable result.** One x86-64 workstation, one environment fingerprint; aarch64 is a statement of installability. CI
  re-classifies the committed records; it does not re-run the tool.
- **Not a release decision.** Whether a release accepts "met where available, 3 of 4" is outside S09.
- **Not that the development runs, the design probes or the spike are evidence.** They are not (§14, §18.7).
- **Not scientific review.** Human numerical and process-modeling sign-off is Frank's.

## 8. Separate findings

- **F-1 (control coverage; for the next specification, not this verdict).** The registered rule is satisfied, but the RC4 family's
  only reference runs a route (L2(c), R2, no reboiler, vapour inlet) on which no control ran. A later reference specification that
  wants a control to guard a sole reference's route would register one there before any run. No action for S09.
- **F-2 (wording, N2).** §6.2 says B4's K is read "from the tool's objects"; the classifier uses SYN-001's closed form. Equivalent here
  (the read-back ties them bit for bit at the registered temperatures). The next amendment could register either form explicitly.
- **F-3 (build log, N3).** The quoted bound on intermediate duties is 2.6e-8 W; the records carry up to 1.06e-7 W. Correct the log.
- **F-4 (A03's scope, N4).** The twin's RC4 reflux ratio appears in `results/biosteam-RC4.json` as the tool's output. A03 scans
  scripts, so it does not fire, correctly. If a later blindness check scans records, it must exempt tool outputs.
- **F-5 (registered behaviour, for information).** Because R3 never passes rule 2, path dependence on the RC3 and RC4 families compares
  only R2 and R4. That is permitted (rule 2d can only exclude), but it is the thinnest path-independence evidence in the package, on
  the states with the fewest references.

## 9. Limitations that must travel into the manifest and the release report

1. **Evidence class.** These comparisons are numerical verification against independent implementations of the same synthetic
   equations. They are not empirical validation, not optimality evidence and not a sensitivity capability. Package status:
   `implemented`; `tested` once A19 is regenerated, and after the reviewer pass, the gate and CI. Not `reviewed`, not `released`.
2. **X31's three-tool reference clause is "met where available, 3 of 4", not "met with two references".** The refluxed absorber (RC4
   family) has one independent reference, BioSTEAM at L2(c). S03's two-tool outcome, "not met, 2 of 4", stands as S03's record. Whether
   a release accepts "met where available" is outside S09.
3. **L2(c) `AGREE`s** (RC4 family, RC5, RC6, RC7) verify our column against BioSTEAM's MESH equations at the state where the harness's
   outer loop meets the specification; the specification equation is S02's or S06's, written by the harness. The temperature kind has
   no native-feature reference in any tool.
4. **Each BioSTEAM control covers one configuration**: RC1 at (L1, R1). No control ran on the total-condenser, no-condenser,
   no-reboiler or L2(c) routes.
5. **Only `P_r`, only the registered states, SYN-001 only.** PC-P shows BioSTEAM's two missing pressure terms combined; our Poynting
   terms stay without an independent check.
6. **Independence is partial and blindness procedural.** Shared SYN-001 constants and S03 §5 semantics; numpy and scipy shared as
   substrate. The spike's exposure (§9.1, quoted in §5.2) and Amendment 1's timing after tool-only development runs are disclosed.
7. **Path independence** is among R1, R2 and R4 on 13 records and among R2 and R4 only on the RC3 and RC4 families. No uniqueness claim.
8. **Our side is least accurate at RC6** (0.0202 tolerance; σ_min 6.06e-4). BioSTEAM is within 1.7e-6 of the twin there. Inside rule 3 by
   a factor of 5.
9. **One platform.** The qualification ran on x86-64, reproduced byte for byte by a second full run on the same machine (A17).
10. **No phase-transition robustness, supported nonideal scope none** (S03 §9, §10.1, §14). §14 and §18.7 of the S09 specification apply
    verbatim.

## 10. For Frank

- **Nothing here needs a decision from you to keep S09 moving.** S09 may close `tested` after the `reviewer` pass, the regenerated
  manifest, the gate and CI.
- **For information.**
  - BioSTEAM agrees with our column on all 17 registered states, and both of its controls disagree as they must.
  - The refluxed absorber (RC4), which neither DWSIM nor IDAES could model, now has one independent check. Its specification is met by
    the harness's loop around BioSTEAM's native column.
  - X31's three-tool reference clause is "met where available, 3 of 4": the best outcome the registered rule allows. "Met with two
    references" would need a second tool that models RC4.
  - Under Q-S09-2's default, no ChemSep package is queued, because BioSTEAM qualified RC4.
- **A decision that is yours, later and outside S09:** whether a release accepts "met where available" for X31. This verdict does not
  answer it.
- **Human numerical and process-modeling sign-off of S09 remains yours.** These verdicts do not stand in for it.

---

## 11. Addendum (2026-10-26): Amendment 2 and the review

**Why this section exists.** §0–§10 were written at `293cb19b` against the specification through Amendment 1 (SHA-256
`e9c25fe7…330a`). They predate the review `docs/reviews/S09-review.md` and Amendment 2 (spec §19, R-751 and R-752), both
committed in `cca49af5`. The text above is unchanged. Where it differs from this section, this section governs. The standing
is the same: agent verdicts, numerical and procedural. This section is not scientific review and does not set `reviewed`.

### 11.1 The hashes against the amended specification: no verdict changes

- **The specification.** Its SHA-256 is now `4ab38942…a533`. `git diff 10adc40b cca49af5 -- docs/derivations/S09-spec.md`
  changes four existing lines and appends §19:
  - the register line;
  - B5's row, which gains a pointer to §19.1 (thresholds unchanged);
  - A09's row, which gains a pointer to §19.5;
  - §18.8's open item, now marked closed.

  No registered value, threshold, tolerance, setting, input, level, case or record changes. §19 says so, and the diff
  agrees.
- **§0's bytes, re-checked at `cca49af5`.**
  - `sha256sum -c SHA256SUMS`: 21 of 21 OK.
  - `comparison.json` `3feb65e5…6423`, `SHA256SUMS` `83a68526…1572`, `qualification/biosteam.json` `cb8b9289…0f72`.
  - The S03 pins `c901d6c9…3f39`, `95ef9bd2…0c67` and `5c7d139c…585d` equal S09 §0.
  - `s09_cases.json` `760ab27f…a813c` equals §18's registration and §19's restatement.
  - Between `293cb19b` and `cca49af5` only five documents change: the review brief, the register, the specification,
    the review and this file. No evidence byte changes.
- **The merge of `main` (S08, `d96c17ae`)** landed while I wrote this section, as `193cb27c`. It touches no file in §0's
  table, so the hashes above hold at `193cb27c` too. It changes `docs/derivations/S03-spec.md` §10.1 and §14 (the phase-transition wording after
  S08). It does not change §6, §7.1 or §17.3–§17.5, the sections these verdicts compose with. §11.5 records what this means
  for limitation 10.
- **Verdicts 1–7 stand as recorded.** Amendment 2 bears on the text in these places only:
  - **§19.1 (R-751).** B5's energy row is a bookkeeping identity under §5.6. §1.2 lists it under rule 2 (1.5e-11 W). Read
    it as a bookkeeping check, not as convergence evidence. Each `AGREE`'s energy convergence rests on rows §1.2 already
    reports. One is rule 2c's adiabatic duty, ≤ 1.06e-7 W against 1e-3 W on every stage without an end specification,
    including the RC4 family's `none`-reboiler stage. The other is rule 2d's duty residual on the RC3 family. No stated
    reason for a label changes.
  - **§19.2(a)** rules that the closed-form K conforms. This closes F-2 (§8).
  - **§19.2(d)** closes WO-S09-1's numpoly item (status table): the fingerprint does not hash it.
  - **§19.3 (R-752).** The classifier fix, §11.2.

### 11.2 The classifier fix and A13: a stated condition

**The assumption.** These verdicts assume that §19.3's fix leaves `comparison.json` byte-identical at `3feb65e5…6423`
(A13). The fix makes the classifier's B3 keep a NaN, as B4 does.

**The check that proves it.** `scripts/s09_reference_comparison.py --check`, run at the fix commit, must exit 0, and §19.5's
A09 NaN mutation must pass.

**Not run.** When I looked, the head was `193cb27c` (after the merge), and the fix was not committed:
`scripts/s09_reference_comparison.py:324` still reads `b3 = r.copy_abs() if r.is_nan() or b3.is_nan() else …`. So
`--check` was not run on the fix, and A13 stands as the condition of these verdicts. If `--check` fails after the fix,
verdicts 1–5 reopen for every pair whose label or worst ratio changes.

**Why byte identity is expected.** Independently of the fix:
- the 19 records contain no `NaN` or `Infinity` token;
- in the 19 selected runs, all 1410 stage flows that B3 reads are present and finite.

So the defect cannot have masked a non-finite value in the committed records.

**A figure that does not match.** The review (F1) says every committed B3 is ≤ 2e-16 mol/s.
`comparison.json → margin → per_pair` gives a largest B3 ratio of 7.25e-5, for RC4. That is 2.2e-12 mol/s, which is §1.2's
figure. Either value is finite and more than four orders of magnitude below 3.1e-8 mol/s. Nothing depends on the
difference.

### 11.3 D19: the review's three blindness disclosures (an addition to §5.2)

The review discloses three exposures (review, "Rulings on the brief's §4 items", item 1: "Disclosures: F5, F6, and
WO-S09-3's one-ulp reflux reading"). §19.4 registers the first two under D19 with §9.1. None of the three affects a label.

**(a) Twin-derived values in `s09_cases.json`.**

> `s09_cases.json` is a registered input of the blind harness. Its claim strings carry two values derived from the twin: C4
> "243.292 tolerances (Q_reboiler)" (line 672) and C6 "T_max 397.3721 K" (line 685). Neither can steer the result. (F5)

*Judgement: affects no label.* Neither value enters a setting, a start, a selection or a check:
- selection is mechanical (§5.3);
- C5 fixes the L2(c) roots;
- rule 2 ties every selected state to the registered model, and §0 recomputed rule 2 from the raw profiles.

243.292 is the size of PC-LI's discrimination. PC-LB's `Hvap` values are registered in §7, and knowing how large a
discrimination is does not move the tool's root. 397.3721 K is one twin temperature, given to 1e-4 K, which is about a
quarter of a tolerance at that temperature. A record's temperatures are the tool's own, and B4 ties each one to its stage's
x and y within 1e-8.

**(b) The clean-or-not stamp is taken at assembly.**

> `harness.head` and `scripts_clean_at_head` are taken at assembly (`s09_qualify_biosteam.py:1590`), not in each case
> process. Run 2's records are not committed. A16 proves the order of the commits, not the order of authorship. (F6)

*Judgement: affects no label. It weakens one provenance sentence.* Read §0's "harness at `fd38124d` (clean at head,
recorded in `harness`)" as "clean when the records were assembled". The classifier computes labels from each record's raw
profile, whatever process wrote it. That the records come from `fd38124d` rests on two facts, as §19.4 states: the run is
deterministic (A17), and the harness diff `c2589694..fd38124d` holds exactly §18.6 items 2–4. This is a limitation of
provenance, not a classification question (§11.5).

**(c) A one-ulp change in how the classifier reads reflux.**

> That reading changed the classifier after values had been seen, at 1e-16 relative. It cannot change a classification,
> and the build log discloses it. (review, item 1)

*Judgement: affects no label.* `view()` (`scripts/s09_reference_comparison.py:197`) forms a total condenser's reflux as the
binary64 difference of stage 0's liquid and the side draw. The reading reaches two places, both only on the total-condenser
cases (RC2 family, RC6):
- **The registered `reflux` quantity** (`s03.tool_quantities`), compared under rule 4. One ulp of a flow below 2 mol/s is at
  most 2.2e-16 mol/s. That is under 1e-9 of the smallest flow tolerance (3.1e-7 mol/s), while a label needs a ratio of 1.
- **The reflux-ratio specification value** (`s03.specification_values`), judged by rule 2c at 1e-4 relative and rule 2d at
  1e-8 relative. One ulp is about 1.6e-16 relative. The largest specification residual of any selected record is 6.4e-4 of
  its threshold.

The exact stored-specification read-back is computed from the registered value, not from this reading. The binary64 form
reproduces the tool's own value (0.6749999999999567 on RC2) and the recorded quantities bit for bit (§0). This is a post hoc
change, made at a scale eight or more orders of magnitude below every threshold, and the build log discloses it.

### 11.4 The worst ratios are our side's distance from the twin

The review ("For the verdict"):

> The larger worst ratios (RC6 `bottom[A]` 0.0202, the RC3 family 0.0017–0.0035) are our side's distance to the twin,
> which S03 already carries.

This is §1.2's finding ("The third corner") and limitation 8. I recomputed it now from the 17 `AGREE` records against
`s03_reference.json`, in 50-digit decimal:
- the largest BioSTEAM–twin distance is 1.009e-5 tolerance (RC4, `L[2]`);
- RC6 is 1.73e-6;
- the RC3 family is 1.4e-6 to 4.6e-6.

**Correction to §1.2's prose.** "BioSTEAM lies within 1.02e-5 of a tolerance of the twin (RC4 `L[2]`)" quotes RC4's
ours–BioSTEAM ratio. The BioSTEAM–twin maximum is 1.009e-5. The stated bound still holds. The table's "Tool vs twin" figure
of 1.0e-5 is the right one, and it agrees with the review's "≤ 1.0e-5 tolerance".

### 11.5 Limitations added to §9 (they travel with it)

11. **Provenance stamp.** The harness head and clean-tree stamp are taken when the records are assembled, not per case. That
    the records come from `fd38124d` rests on A17 and the harness diff (§19.4). Run 2's records are not committed.
12. **Twin-derived values.** `s09_cases.json`'s claims carry two values derived from the twin: C4's 243.292 tolerances and
    C6's 397.3721 K. They are disclosed under D19 with §9.1 (§19.4).
13. **A post hoc classifier reading.** One classifier reading, WO-S09-3's total-condenser reflux, changed by one ulp after
    values had been seen. It is disclosed, and it moves no label.
14. **A13 is a condition.** These verdicts hold for `comparison.json` `3feb65e5…6423`. They require the classifier after
    §19.3's fix to reproduce it byte for byte (§11.2).
15. **Limitation 10, after S08.** Since the S08 merge (`193cb27c`), S03's text reads "no phase-transition robustness beyond
    S08's block re-entry". For S09 nothing changes in substance:
    - no selected record has a one-phase stage (§1.2), so S09 carries no evidence on one-phase sections;
    - S08's block re-entry is S08's evidence, not S09's;
    - S09 reads S03's committed `ours-*.json`, pinned by hash. Whether the column after S08 still reproduces them is S08's
      identity evidence. This section does not check it.

**What would change this addendum.** Any of these reopens it:
- `--check` fails after the fix;
- a later merge touches a file in §0's table, or S03 §6, §7.1 or §17.3–§17.5;
- a later finding shows that a twin-derived value entered a harness setting.
