# T06 — verdicts on evidence (reference comparisons, the nominal robustness gate, no false verification)

**Lane:** design (`verdict`). **Date:** 2026-09-26. **Branch:** `wp/T06` at `1fdc717` (the ensemble
software is `f636452`; `f636452..1fdc717` changes one T05b test and three documents, no `src/`,
`benchmarks/` or harness file). **Brief:** `docs/briefs/T06-verdicts.md`.
**Standing:** these are agent verdicts, numerical and procedural. They are not scientific review.
`review.numerical` and `review.process_model` stay `pending` for Frank's sign-off, and nothing here
claims them. Nothing was re-run except what the brief allows: the comparison table was recomputed
from the committed JSON, the ensemble reports from the run files, and the gate tests of the three
subjects (`tests/test_t06_w8_references.py` 130 passed; `test_t06_w6_ensemble.py`,
`test_t06_w19_closure.py`, `test_t06_w18_policy.py`, `test_t06_w18_refinement.py` 69 passed).

## The verdicts

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | D19 / V16 comparison clause: REF-01…REF-08 × DWSIM, IDAES, and the positive controls (spec §9 as amended, A47–A54, A83; plan §6.4) | **MET.** All 16 (fixture, tool) pairs are `AGREE`. PC-1 (DWSIM) and PC-2 (DWSIM and IDAES) are `DISAGREE`, as they must be. (PC-1, IDAES) is `not_applicable`, a registered absence. V16 counts 8 fixtures by at least one tool and 8 by both. Independence and blindness are met as registered, with one disclosure that must travel (IDAES ε, §1.4) |
| 2 | V20 robustness clause on scoring run 2 (spec §7.1–§7.3 as amended, A28–A31; plan §6.2, §6.5; R-087) | **MET on `ref-x86-64` and on `ci-aarch64`.** S = 434 of 440 on each (`S_min` = 418). No `F-CRASH` and no `F-OTHER-ROOT`. Run 2 is a **legitimate** re-score under the preregistration rules, subject to four qualifications that travel (§2.3). Run 1's **FAIL stands**, as recorded (S = 431, four unexplained `F-OTHER-ROOT`). |
| 3a | V20 "no false verification": run 2 (both architectures) and the corpus at `1fdc717` | **MET.** No `VERIFIED` state lies outside S3 (worst 0.0968 of an allowance). Every `FAILED` certificate is `false_success_detected`. The corpus's A16/A19/A20 tests are green on both architectures |
| 3b | The same clause for run 1 | **NOT MET, and it stays recorded that way.** Run 1 has four `F-OTHER-ROOT`s that §7.2 cannot explain. It also has one missed false success: NET-11 start 16 was `VERIFIED` with a false `TWO_PHASE` label and was counted as a SUCCESS. Run 1 is not re-judged |

Separate status lines (evidence the registered text requires that does not yet exist; none is a
gate term):

| Item | Status |
| --- | --- |
| A90: run 2's records carry, per attempt, whether ADR 0018's refinement fired, and the report counts fired/kept/reverted/abandoned | **NOT MET.** The harness records neither, and no code writes them (`grep terminal_refinement` finds only `numerics/newton.py` and two tests). On `ref-x86-64` the counts can be reconstructed from run 1 → run 2 differences (§2.4). On `ci-aarch64` they cannot |
| A95: the campaign manifest keeps run 1 unedited and run 2 as a separate record | **Pending.** No manifest exists yet. Every run file is outside the repository (§0) |

---

## 0. The evidence judged, and its provenance

These verdicts apply to the files below, identified by SHA-256. They do not transfer to any other
record. The manifest must cite these bytes, or bytes shown equal to them.

| Record | Produced by / where | SHA-256 |
| --- | --- | --- |
| Run 1, local | `scripts/t06_ensemble.py run` at `dfa7d09`, `ref-x86-64` (Threadripper PRO 5965WX, Python 3.13.5, numpy 2.2.4, scipy 1.15.3), `T06-revision-v1` `27b6c8d6…`; scratchpad `scoring/ensemble_x86.json` | `b82964be42580bb2cf1ffe94706ceb617108b35ee0b735cda298bf4fe2480cc6` |
| Run 2, local | the same host, `f636452` per `docs/T06_DECISIONS.md`, `T06-revision-v2` `c03d7205…`; scratchpad `scoring/run2_x86.json` | `c15924e6dd8205122a041348502d2634a56d687c9e79ce92408e0a0295d7d85e` |
| Run 2, CI x86-64 | dispatch run 36270294833, job `ensemble (ubuntu-latest)`, head `f636452`, AMD EPYC 7763, Python 3.13.15; artifact `ensemble-ubuntu-latest` (expires 2026-12-25) | `8768b15043d9e16e37e787e6bf41039391d67ba5e5fd71292c9621c92a9c688b` |
| Run 2, CI aarch64 | the same run, job `ensemble (ubuntu-24.04-arm)`; artifact `ensemble-ubuntu-24.04-arm` (expires 2026-12-25) | `c1f89ee86d3fe05b461308a283f368a862a1121082ad114e3eae677650e24f91` |
| Run 2 report / replay, local | scratchpad `scoring/run2_report.txt`, `run2_replay.txt` | `eb24251e…`, `b1a41a44…` |
| Starts | `benchmarks/t06/ensemble/starts-nominal-v1.json`, recorded in all four run files | `3a7bd49c66493744753d1eac554101317c931e0ef51d9154d6f7cab3124fef82` |
| Reference comparison | `benchmarks/t06/references/comparison.json`, `results/` (every file matches `SHA256SUMS`), twin `e97f61ce…` | recomputed identically by `scripts/t06_reference_comparison.py --check` |

**Provenance defects, none of which moves a number judged here:**

- **P1.** The run files live only in the session scratchpad (`/tmp/...`) and in CI artifacts that expire on 2026-12-25. `evidence/T06/artifacts/` is empty, and the commit `bbabf9a` that records run 2 adds a log entry and nothing else. Before any manifest cites them, they belong under `evidence/T06/artifacts/`, referenced by hash.
- **P2.** The CI records label themselves `"machine_class": "ref-x86-64"` on both runners, the aarch64 one included. `benchmarks/t06/generator.py:695` hard-codes the string, and `scripts/t06_ensemble.py` reuses `generator.host()` for run records. The `architecture` field is correct (`aarch64`), and the aarch64 identification above rests on it and on the CI job name. Spec §7.5 registers `ci-x86-64` and `ci-aarch64`, so the field is wrong.
- **P3.** No run record carries the commit it ran at, a lock hash, or spec §6.6's `cache_condition`. The local run 2's commit comes from the decisions log. It is corroborated independently: all 437 final states and all 440 classes are bit-identical to the CI x86-64 run at `f636452`, on a different CPU.
- **P4.** The dispatch run 36270294833 concluded `failure`. Its `check (ubuntu-24.04-arm)` job failed on T05b B34 (a)'s closure-value pin, a test that the ensemble jobs do not use. At `1fdc717`, CI 36271572251 is green on both architectures, and its `identity` job (A45) passes.

---

## 1. Verdict 1: the eight reference comparisons (D19; V16's comparison clause)

### 1.1 Criteria as registered

§9.4: `|ours − tool| ≤ a_k + 1e-6 |v_twin|`. §9.5 applies rules 1, 2, 2b, 3 and 4 in order. The
positive controls must `DISAGREE`. The verdict agent may not change a tolerance, a setting or a
mapping. §9.6 requires blind tool scripts and qualification. Plan §6.4 requires the same model
semantics, preregistered tolerances, access kept apart from science, and no reconciling by tuning.
D19's minimum evidence is "matched-model inputs, independence disclosure and verdicts".

### 1.2 Per (fixture, tool)

The classifications are recomputed from the committed JSON, the twin and (A50, run here) a live
solve of our side. Our side is `CONVERGED`/`VERIFIED` with no limitation and no non-passing check
on every fixture: REF-01…07 and PC-2 under `T06-revision-v2`, REF-08 on the tear path under
`SYN-001-K03`.

| Fixture | DWSIM | worst (ratio to tolerance) | IDAES | worst (ratio) | IDAES rule 2b shift |
| --- | --- | --- | --- | --- | --- |
| REF-01 mixer | **AGREE** | S3.n.B 1.5e-10 | **AGREE** | S3.T 1.7e-7 | 4.8e-12 K |
| REF-02 splitter | **AGREE** | S3.n.C 1.7e-10 | **AGREE** | S3.n.A 2.0e-10 | 1e-12 K |
| REF-03 heater | **AGREE** | S2.vap.A 4.6e-8 | **AGREE** | S2.vap.A 3.8e-8 | 1e-13 K |
| REF-04 ideal flash | **AGREE** | S3.n.B 2.9e-9 | **AGREE** | U-FLASH.Q 1.4e-8 | 1e-13 K |
| REF-05 valve | **AGREE** | S2.vap.A 1.3e-6 | **AGREE** | S2.vap.A 3.0e-9 | 0 K |
| REF-06 liquid pump | **AGREE** | S2.T 1.9e-10 | **AGREE** | S2.T 7.4e-10 | 5e-14 K |
| REF-07 conversion reactor | **AGREE** | S2.n.B 2.2e-10 | **AGREE** | U-RX.Q 2.5e-7 | 7.6e-13 K |
| REF-08 recycle (SYN-001-nominal) | **AGREE** | S7.n.C 4.0e-6 | **AGREE** | U-HEAT.Q 3.0e-4 | 5e-9 K |
| PC-1 (REF-04, ΔH_vap = L_i) | **DISAGREE** (required) | U-FLASH.Q 205 | `not_applicable` (registered absence) | — | — |
| PC-2 (TP flash, 370 K, 1.5e5 Pa) | **DISAGREE** (required) | S2.n.B 4 581 | **DISAGREE** (required) | S2.n.B 4 581 | 1e-13 K |

Reason for every `AGREE`: rules 1, 2, 2b (IDAES) and 3 do not fire, and every registered quantity is
within §9.4. Rule 1 does not fire because the fingerprints equal `docs/reference-environments.md` §3
(A48). Rule 2 does not fire because each tool's own balance closes against 3.1e-8 mol/s: to ≤ 4.4e-12
on the REF fixtures (DWSIM REF-08, the largest; IDAES ≤ 4.8e-13) and to 1.4e-11 on DWSIM PC-2. The positive controls move by the predicted effects: `−P_r v V` = −13.6 W on the flash duty,
and the missing Poynting factor on `S2.n.B` (A51). The harness therefore sees the effects it exists
to see.

**Margin, reported rather than used.** The largest ratio in any counted pair is 3.0e-4 (IDAES,
REF-08 heater duty). Every `AGREE` would therefore survive a tolerance more than 3 000× tighter. The
registered relative term `1e-6 |v|` makes the temperature tolerance at 320–360 K about 33× S3's
allowance, and it catches a DWSIM latent-offset error on REF-05 by only 1.02× (§9.4 discloses this).
The observed agreement does not depend on that looseness. PC-1 carries the latent-heat
discrimination at 205×.

### 1.3 V16's counts (§9.5, A53)

Compared by at least one tool: **8 of 8**. Compared by both: **8 of 8**. The plan asks for at least
two. Every retained `DISAGREE` is in the dossier: the positive controls, and W8's default-ε IDAES
records with their pre-2b `DISAGREE` table (REF-03 1.36, REF-08 302). No pair is
`NOT_COMPARABLE(access)`.

### 1.4 The rulings that set tool inputs: when each was fixed, and whether it is tuning

Each ruling was dated against the first comparison (W8's tool records, `1cc46e2`, 2026-09-26 13:12).

| Ruling | Fixed | Tuning? |
| --- | --- | --- |
| DWSIM `ΔH_vap,i := L_i + P_r v_i`, and the same value as the formation datum | Spec `da428a2`, 2026-09-25 23:37, before any comparison | **No.** It follows from the equation forms (DWSIM's `h^V − h^L = ΔH_vap − P v_i`), is generator-checked, and was read back from every DWSIM record (A 25 010 J/mol; PC-1 carries the unmapped 25 000) |
| IDAES `constr_viol_tol = 1e-9` for every final solve | M6 qualification (blind, 2026-09-25), then registered uniformly by A1 | **No.** It was set for convergence at the Pa-row binary64 floor, judged on the tool's own self-consistency before any comparison, and applied to every fixture. Every IDAES log ends "Optimal Solution Found" |
| MUMPS in every IDAES solve, initializers included; HSL MA27 unused | Registered by A1 | **No.** It is a disclosure item (D19). Every final-solve log names MUMPS, none names MA27 |
| REF-07's DWSIM extent `ξ = X_A n_A,in/|ν_A|` | A1, before W8 | **No.** It is disclosed in every DWSIM record. Rule 2's A row is an identity there, and B and C carry the check. Rule 4 compares all three outlet flows and the duty |
| IDAES SmoothVLE `eps_1 = eps_2 = 1e-8 K`, with rule 2b | Amendment 2, `1f07cdc`, 2026-09-26 13:44, **after** W8 showed IDAES `DISAGREE` on REF-03 and REF-08 | **Not tuning, but post hoc, and disclosed as such.** The mechanism was identified from IDAES's own variables: `T_eq − T = ε₁/2 = 5.0e-3 K` at REF-08's bubble-point recycle, and no result of ours was needed to see it. The value comes from the formula and the registered allowance (the shift is bounded by `a_T/1000`), not from agreement. It applies uniformly to every IDAES record, including the six that already agreed. The re-run was blind (A52 static check passes, and the flags were read first). The default-ε records are retained. PC-2 (IDAES) still `DISAGREE`s at 4 581×, so the harness still sees a real equation difference. **Corroboration:** DWSIM, whose inputs were all fixed before any comparison, agrees on all eight on its own |

**Independence (D19 disclosure) as registered is met.** Neither tool shares code, data files or a
property package with this project (`docs/reference-environments.md` §4.3, §5.0). DWSIM's bundled
databases and external thermodynamics are unused. The shared element is the model definition,
SYN-001, and that sharing is by design. **Blindness as registered is met.** The tool scripts import
neither `process_runtime` nor the twin's output (A52, run here). The M6 qualification preceded every
comparison.

### 1.5 Alternatives rejected

- **Count IDAES at its default smoothing, so REF-03 and REF-08 are `DISAGREE`.** Rejected. Rule 2b classifies those records `NOT_COMPARABLE(semantics)` as registered. They solve a smoothed equation set that SYN-001 does not define. They stay in the dossier.
- **Discount the IDAES column because ε was set after a disagreement.** Rejected. The table above shows the setting was derived, uniform and blind. V16's counts would not change either way: under §9.5 a `DISAGREE` counts as a comparison.
- **`NOT_COMPARABLE` for DWSIM REF-07 because its extent is inferred.** Rejected. Rule 2 still binds on B and C, and rule 4 compares every registered quantity independently of ξ.
- **A tighter verdict tolerance "because the margins allow it".** Rejected. The verdict agent may not change a tolerance.

### 1.6 What would change it

- A tool record shown to have read our results or the twin.
- A fingerprint mismatch, or a re-run of `spikes/references/t06_qualify.sh` that does not reproduce the committed records' content.
- A live solve of our side that no longer matches its committed record (A50).
- Evidence that ε = 1e-8 K was chosen by scanning agreement.
- A change to SYN-001's definition, a mapping, a tolerance, or a tool version. Each of these requires re-qualification and a new verdict.

### 1.7 What it does not establish

**This is numerical verification, not validation.** It verifies second and third implementations of
the same synthetic equations. It is not empirical validation: no real chemistry, no data. All four
corners (ours, twin, DWSIM, IDAES) share SYN-001's definition, so an error in that definition cannot
be seen here. The tool-side scripts were written by this project's build lane. The IDAES `Psat`
class is a user-written transcription of SYN-001's formula.

**The IDAES result is about its near-sharp limit.** It says nothing about IDAES at its default
smoothing, about other tool versions, or about HSL solvers.

---

## 2. Verdict 2: the nominal robustness gate on run 2

### 2.1 Criteria as registered

§7.3 passes iff S ≥ 418 of N = 440, with no unexplained `F-OTHER-ROOT` and no `F-CRASH`, on
`ref-x86-64` and separately on `ci-aarch64`. §7.1 counts a start as a success if S1–S4 hold: rescued
starts count, S3 applies the T02 §6.4 allowances against the registered root, and S4 applies the 60 s
ceiling. The classes are those of §7.2, and §7.2 (A4) is not widened. Plan §6.2 requires budgets and
ceilings registered before scoring and starts committed before any solve. Plan §6.5 requires the full
registered gate to be re-run after a solver-policy change. R-087 keeps run 1 as recorded and lists
what may not change.

### 2.2 The numbers

| Run | Machine | S (first + rescued) | Failures | Gate |
| --- | --- | --- | --- | --- |
| 1 (`dfa7d09`, v1) | ref-x86-64 | 431 (367 + 64) | F-OTHER-ROOT 4 (THM-09/1, /2, /5, /10 at 1.005, 3.447, 1.010, 1.429 allowances), F-BUDGET 3 (THM-08/3, /12, THM-09/4), caught 2 (THM-09/3, /18) | **FAIL**, stands |
| 2 (`f636452`, v2) | ref-x86-64 | **434** (370 + 64) | F-BUDGET 3 (the same three), caught 3 (THM-09/3, /18; NET-11/16) | **PASS** |
| 2 | ci-x86-64 (EPYC) | 434 (370 + 64) | identical to ref-x86-64, class by class and bit by bit in all 437 final states | PASS (reported; not a registered class for the gate) |
| 2 | ci-aarch64 | **434** (367 + 67) | F-BUDGET 4 (+THM-09/3), caught 2 (THM-09/18, NET-11/16) | **PASS** |

A28 is met: 0 `F-CRASH` in every file. A29 is met: 0 `F-OTHER-ROOT`, and the worst S3 ratio of any
`VERIFIED` start is **0.0968** (STR-01/18, `S6.T`) on all three run-2 machines. A30 is met: 434 ≥ 418
on both registered classes.

A31 is met. Recomputing the report from each file with the committed harness reproduces every
headline. I also recounted independently, outside the harness's report path. For S1–S4 I re-derived
S3 from each record's state against the registered roots (the twin, the P01 oracle, and T02's A02
sweep, all independent expectations), and the recomputed ratios equal the recorded ones exactly. I
computed the Clopper–Pearson bound at S = 434 by root-finding on the binomial tail and got
0.9732639029561057. The twin's table gives 0.973263902956.

On the other assertions:

- **A32:** estimates never exceed the exact norm, with no status disagreements (437 and 436 matrices).
- **A33:** 0 failures.
- **A34:** replay MATCH 28 of 28 on each of the three machines.
- **A84:** ten acyclic cases, as the text now says.

### 2.3 Is run 2's pass legitimate under the preregistration rules?

**Yes.** Here is what I checked, and the four qualifications that must travel with it.

What did not change between run 1 and run 2 (verified, not taken from the log):

- **The starts.** The file is `3a7bd49c…` in every run file, published by W16 before run 1. Regenerating it on both CI runners changes no float. The only differences are the 19 per-case `policy` labels and the host fields, 21 and 22 differences in total.
- **The scoring code.** Between `dfa7d09` and `f636452`, `benchmarks/t06/ensemble.py` changes only the A33 reporting. `classify()`, the allowances, `CEILING_S` and `S_MIN` are untouched.
- **The registered roots.** Recomputing run 1's S3 ratios with today's roots reproduces them exactly (the twin's A4 diff is additive).
- **The budgets and the ceiling.** `T06-revision-v2`'s document differs from v1's in exactly `policy_id` and `globalization.eo_core`, checked field by field. The budgets remain 50 iterations, 5 attempts, 10 000 property calls and one recovery edge. The ceiling remains 60 s. Hashes: `c03d7205…` and `27b6c8d6…`.
- **Run 1's record.** Recomputed today it is still S = 431 and FAIL.

What did change, and why neither change inflates S:

1. **ADR 0018, a solver change.** It never changes an outcome (D4), so it can move a start only through the certified state's accuracy.
   - On `ref-x86-64` it moved exactly the four THM-09 `F-OTHER-ROOT`s to SUCCESS.
   - Run 1's count had already cleared 418. The remedy removed the failing gate *term*. It did not buy the rate.
   - It has no case- or start-specific parameter. Its threshold is S3's allowance/10, derived from S3 and ADR 0007's margin, not fitted to the four.
2. **§8.8, a verifier change.** It replaced a vacuous check with a real one, so it can only turn passes into failures. It cost run 2 one start (NET-11/16).

The class-by-class comparison of run 1 and run 2 on `ref-x86-64` shows exactly these five predicted
moves and no others.

**Qualifications that travel:**

- **(a) §7.3's sentence contradicts the amendment's edit.** Taken literally, "nothing in §6 may be changed after any ensemble solve has been seen" (§7.3) contradicts Amendment 4's edit of §6.6, which registers a new revision-path policy after run 1. I decide under R-087 and §6.6 (A4) for three reasons. They are the later and specific registration. The execution authority, plan §6.5, anticipates exactly this ("Do not skip the full registered gate after changing a solver policy"). And the purpose of §7.3's sentence (no outcome-driven change to what scores a start) is met item by item above. The sentence itself is still in the spec, unamended, and a reader who wants a different answer can cite it. **Finding F-1:** amend §7.3 to R-087's wording. That is the design lane's job, not the build lane's.
- **(b) Run 2 re-scores the starts that exposed the defect.** Run 2 is not an out-of-sample test of `T06-revision-v2`: the remedy was designed after four of these 440 starts failed. The selection effect is confined to one mechanism, because the only class changes are the predicted five. Even so, the Clopper–Pearson bound of 0.9733 is start-sampling uncertainty for a solver whose last change was informed by these draws. The smallest measurement that would remove this qualification is a fresh draw of 440 starts under a new key prefix, scored under `T06-revision-v2` on both classes and reported, not gated. The registered criteria do not require it.
- **(c) Frank's approval rests on the decisions log.** Frank approved ADR 0018's enum widening at `bc45345` (21:23), before the widening commit (`9e5a7d2`, 22:10) and before run 2 (22:39). The ADR's header and register entry R-085 still read "pending Frank's approval". **Finding F-4:** update both. I cannot verify the approval beyond the log.
- **(d) The gate holds on each architecture, but per-start outcomes are not portable.** `ensemble-compare` lists one classification disagreement: THM-09/03 is `F-FALSE-SUCCESS-CAUGHT` on x86-64 and `F-BUDGET` on aarch64. It does not list three further differences in rescue status: STA-02 starts 0, 2 and 17 succeed on their first solve on x86-64 but are rescued on aarch64. 217 of 437 final states differ in bits between the architectures. A35 treats all of this as report, not promise.

### 2.4 A90, reconstructed where the evidence allows

A90's per-attempt refinement record does not exist (see the status line above). On `ref-x86-64`, 420
converged starts have bit-identical final states and identical event streams in runs 1 and 2. No
refinement iteration was recorded in them, which is A87 (b)'s signature of a rule that did not fire. Exactly 17 starts differ in both state and events, and each
by one trailing iteration (`jacobian`, `linear_solve`, `step_accepted`):

- NET-03/8, /19
- NET-10/0, /4, /8, /11
- NET-11/12
- STR-01/5
- THM-07/0, /5
- THM-09/1, /2, /5, /6, /10, /19
- THM-10/7

All 17 are `VERIFIED`, at S3 ≤ 2.17e-5. They include every one of run 1's 14 `VERIFIED` starts that
sat above 0.1 of an allowance, which is ten more than the four the remedy was designed for. No start
differs in events only, so no reverted refinement is visible. The inferred counts on x86-64 are
therefore fired 17, kept 17, reverted 0, abandoned 0. None of the three F-BUDGET starts differs from
run 1, so no refinement touched a budget run-out.

On aarch64 there is no baseline. THM-09/03 there follows the pattern of the three known F-BUDGET
starts: PHASE_UPDATE_REQUIRED, then BOUND_BLOCKED, then a third attempt exhausted in the band route.
No attempt closed `CONVERGED`. Whether a refinement fired inside that third attempt cannot be read
from the record, so the W18 executor defect ("a budget run-out inside a refinement is marked
`BUDGET_EXHAUSTED`") is neither shown nor excluded there. The start's class is a failure on every
branch, so the gate is unaffected. The smallest measurement that settles it: re-run that one start on
the aarch64 runner under `T06-revision-v2` with the attempt-closing messages captured, which is what
implementing A90 in the harness would give.

### 2.5 Alternatives rejected

- **Treat run 1 as T06's gate result, so V20 fails and T06 is not `tested`.** Rejected. Plan §6.5 prescribes a full re-run after a solver-policy change. R-087 keeps run 1 on record without making it the last word.
- **Re-judge run 1 using Amendment 4's diagnosis** (the four are "the registered root within `b`"). Rejected. §7.2 (A4) and R-087 forbid it, and it would flip a failed gate by relabelling.
- **Declare run 2 illegitimate until a fresh draw is scored.** Rejected. That would impose a criterion the registration does not contain. It is recorded as qualification (b), with the measurement that would remove it.
- **Gate on the Clopper–Pearson bound.** Rejected. Frank's Q7 settled the point estimate. For information, the bound would also pass: S ≥ 426 is needed and S = 434.
- **Count `ci-x86-64` in place of `ref-x86-64`.** Not needed: the two are bit-identical.

### 2.6 What would change it

- An `F-OTHER-ROOT` or `F-CRASH` in any re-run of this software on either registered class.
- Run files that do not hash to §0's values.
- Evidence that something which scores a start (starts, `classify`, allowances, budgets, ceiling, roots) differed between the runs.
- Any solver or verifier change after `f636452`. Plan §6.5 then requires a new full run.
- A start-specific or fitted element found in ADR 0018.

A fresh-draw holdout with a materially lower rate would not flip the registered gate. It would
change what the release report may say.

### 2.7 What it does not establish

**Scope of the 95 %.** The 95 % is over the start distributions of these 22 registered cases, under
`sha256-counter-v1` at ±20 % of scale. It says nothing about other process designs: 440 starts are
not 440 designs.

**Acyclic cases.** On the ten acyclic cases, `p_c` says nothing about Newton's basin. `S^first` is
370 on x86-64 and 367 on aarch64, with lower bounds 0.809 and 0.802, and no threshold applies to it.
THM-08's and THM-09's `p_c^first` measure recovery from single-phase openings, not a near-root basin.

**Solution accuracy is the solver's, not the certificate's.** ADR 0018 makes the solver deliver the
accuracy, and `VERIFIED` still promises residual accuracy only (K04 F3). The refinement does not
apply to the tear path, to NET-05's policy, to `k = 0` exits or to homotopy correctors.

**No performance claim.** The 60 s ceiling is a hang guard.

**Portability.** Two registered machine classes pass. That is not a portable per-start result (§2.3 d).

---

## 3. Verdict 3: no false verification

### 3.1 Criteria as registered

- V20: "no adversarial false verification".
- Spec §7.2: every `F-OTHER-ROOT` is a potential false verification, and the clause fails until a twin evaluation shows a genuine second root. A4 does not widen this.
- A29: zero unexplained `F-OTHER-ROOT`.
- The corpus's A16 (ADV-06 H never `VERIFIED`), A19 (VER-01…05 as registered) and A20 (no case of another kind ends `VERIFIED`, except the four registered sub-fixtures).
- §8.8: a false two-phase label fails the closure.

### 3.2 Run 2: met

**No `VERIFIED` state is far from its registered root.** On all three run-2 machines, every
`VERIFIED` start is within 0.0968 of every S3 allowance on every registered coordinate (8 to 71
coordinates per case). The ratio was recomputed from the recorded states against independent
references.

**Every caught false success is labelled and correct.** Every `FAILED` certificate carries
`false_success_detected`, and each is the predicted one:

- **THM-09/3 and /18:** the trivial `V → 0` root, failing on energy balance and independent split. On aarch64, /3 never reached a certificate (F-BUDGET).
- **NET-11/16:** the false `TWO_PHASE` label, failing on `phase_admissibility.U-HEAT.S4.closure` alone.

**No caught false success is missed.** No start that failed on one machine is `VERIFIED` on another.
Every `VERIFIED` certificate is `NO_RANK_LOSS_DETECTED`. The branch census finds one label set per
case on every machine, whereas run 1 found two for NET-11. This corroborates that no mixed-label
`VERIFIED` pair survives.

### 3.3 The corpus at `1fdc717`: met

The CI gate is green on both architectures (36271572251: `check` × 2, `identity`). This covers A20
(`PENDING` is empty; every case is measured by a named test), A19 (VER-02/03's identity refusal
included), and A16–A18 (ADV-06).

Under W19's substitution of §8.8's closure, the full suite moved exactly four registered
expectations, and none of them was a `VERIFIED` certificate becoming `FAILED`. T05b B34 (a)'s four
moved from `UNVERIFIED` to `FAILED`, all `false_success_detected`. B16 and B26 stay `VERIFIED`, and
one T04 fixture changed only its tolerance and reference. The closure being vacuous since K03 has
therefore not left a false `VERIFIED` in any closed package's registered set.

### 3.4 Run 1: not met, and recorded

- **The four THM-09 `F-OTHER-ROOT`s** fail §7.2's clause as registered. Amendment 4's diagnosis is that the certificate's own claim is true: the rows hold at `x_final`, and `b` covers the 1.005–3.447 allowances. That diagnosis is not an explanation under §7.2 and does not change the record.
- **NET-11 start 16 is a missed false success.** Its certificate was `VERIFIED` and claimed `U-HEAT TWO_PHASE` with `S4.V = 6.3e-11 mol/s` at 370 K, 3.34 K below the liquid's bubble point. The phase-admissibility closure passed only because it was identically zero. S3 could not see the error, because the phase amount is below the flow allowance, so run 1 counted the start as a SUCCESS. It was surfaced by the branch census and fixed by §8.8.

### 3.5 What would change it

- Any certificate found `VERIFIED` while false on re-examination, for example through another check that is vacuous by construction.
- An `F-OTHER-ROOT` in any re-run.
- A registered `VERIFIED` case failing an independent check.

### 3.6 What it does not establish

- **Checks can only catch what they check.** §8.8 makes the closure real, but nothing here shows that no other check is vacuous. The run-1 NET-11 case shows that S3 and the residual checks cannot see a false label on a vanishing phase.
- **Saturation, not amounts.** §8.8 checks saturation temperature, not phase amounts. At an ADR 0013 D3 unresolved split, the amounts remain unchecked.
- **The solver can still emit the false label.** The solver-side conversion is Q22, not in T06. NET-11/16 remains a failure.

---

## 4. Separate findings

- **F-1 (criterion text).** §7.3's "nothing in §6 may be changed after any ensemble solve has been seen" contradicts Amendment 4's §6.6. Replace it with R-087's list ("nothing that scores a start changes; a solver or verifier remedy re-runs the full gate on both classes"), so the registered text says what was done.
- **F-2 (A90).** Implement the per-attempt refinement record and the fired/kept/reverted/abandoned counts in the harness. Until then, the manifest may cite §2.4's x86-64 reconstruction as inference, not as A90.
- **F-3 (records).** Fix P1–P3 before the manifest:
  - archive the run files under `evidence/T06/artifacts/` by hash;
  - correct the `machine_class` label;
  - record the commit, the lock hash and `cache_condition` in the run document.
- **F-4 (documents).** ADR 0018's header and R-085 are stale ("pending Frank").
- **F-5 (outside these verdicts, for the reviewer).** T05b B34 (a)'s moved closure values are not reproducible across x86-64 runners at the same commit. The check job passed in 36270294833 and failed in 36270210365 at `f636452`, landing 16.16 K against 23.78 K. The verdict (`FAILED`, closure alone, ≥ floor) holds everywhere. The test's floor constant (9.4e-4 K) is below A92's registered "≥ 9.5e-4 K", as the build lane has already flagged.

## 5. Limitations that must travel into the manifest and the release report

1. **Evidence class.** The reference comparisons are numerical verification against independent implementations of the same synthetic equations. The ensemble is numerical robustness evidence. Neither is empirical validation or optimality evidence. Status: `tested`. Not `reviewed`, not `released`.
2. **IDAES.** IDAES agrees at the registered near-sharp SmoothVLE ε, a setting ruled after W8's disagreement. At the default smoothing it disagrees on REF-03 (1.36×) and REF-08 (302×), and those records are retained.
3. **Run 1 stands.** Run 1 is the failed first score. Run 2 is the passing re-score after a solver remedy (ADR 0018) and a verifier correction (§8.8), on the same 440 starts. The Clopper–Pearson bound (0.9733) is not an out-of-sample estimate for `T06-revision-v2` (§2.3 b).
4. **Platform dependence.** The gate passes on `ref-x86-64` and `ci-aarch64`. Per-start classification differs across architectures at THM-09/03, and rescue status differs at STA-02/0, /2 and /17.
5. **The two quoted statements** (the rescue sentence, and "no statement about other process designs") and THM-08/THM-09's single-phase openings.
6. **Run 1's missed false success.** NET-11/16 was a false verification the gate could not see, and the §8.8 closure had been vacuous since K03.
7. **Provenance.** The provenance defects P1–P3 hold until they are fixed. A90 is not met.

## 6. For Frank

- **Nothing here requires a decision to keep T06 moving.** The three verdicts can be cited as they stand, with §5.
- **Optional (a value judgment only you hold):** do you want a fresh-draw holdout ensemble under `T06-revision-v2`, reported and not gated, before T08 cites V20 in a release report? Default if you do not answer: **no**, and §2.3 (b) and §5.3 travel as limitations.
- **For information:**
  - IDAES agrees only at a tool setting the design lane ruled after seeing a disagreement. The ruling was derived and uniform, and I judge it not to be tuning (§1.4), but it is post hoc.
  - Your approval of ADR 0018 is recorded only in `docs/T06_DECISIONS.md`. The ADR and the register still say "pending".
- **Human numerical and process-modeling sign-off** of T06 remains yours. These verdicts do not stand in for it.
