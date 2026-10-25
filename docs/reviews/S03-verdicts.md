# S03 — verdicts on evidence (column reference comparisons, X31's reference clause, D19's column part)

**Lane:** design (`verdict`), work order WO-S03-5 (spec §12, as amended by §17.10 and §18.8). **Date:** 2026-10-25.
**Branch:** `wp/S03` at `5a06e53c`. The comparison is `959131dc`: `benchmarks/s03/references/comparison.json`, SHA-256
`5c7d139c0547f17bfa318f33b106cdb5749b9eaacbccb07cf1dedd570593585d`. Its manifest is
`evidence/S03/959131dcfc9ec9b2a068cb89b4cd73b989dfc326/manifest.json`: `implemented`, 21 of 24 checks pass, and A17 fails
because this document did not exist. **Authority:** `docs/derivations/S03-spec.md` (SHA-256 `5584acba…23dc`): §7, §11–§14,
Amendment 1 (§17) and Amendment 2 (§18). The form follows `docs/reviews/T06-verdicts.md`.

**Standing.** These are agent verdicts, numerical and procedural. They are not scientific review. `review.numerical` and
`review.process_model` stay `pending` for Frank's sign-off, and nothing here claims them. This document does not set
`reviewed`, and it does not replace the package's single `reviewer` pass (§12), which has not yet run. No tool was run. §0
lists what was run.

## The verdicts

| # | Criterion (as registered) | Verdict |
| --- | --- | --- |
| 1 | Classification of every (case, tool) pair: §7.1 rules 0–4, with §17.3, §17.4 and §18.4, on the committed records (40 pairs) | **Confirmed as recorded.** 23 `AGREE`. 2 `DISAGREE`, both controls, as required. 13 `NOT_COMPARABLE(capability)` (rule 0). 2 `not_applicable`. No genuine `DISAGREE`, no rule 1, no rule 3. An independent recomputation gives the same label for 40 of 40 pairs, and the same worst quantity and ratio for every rule-4 pair (§0) |
| 2 | Positive controls: §17.3, with IDAES's two controls by §18.3 (A11) | **MET.** (PC-L, DWSIM) is `DISAGREE`: maximum 243.289 tolerances, 22 of 29 quantities outside. (PC-LI, IDAES) is `DISAGREE`: maximum 243.292, 22 of 29 outside. Each tool lands within 0.0326 (DWSIM) and 4.6e-4 (IDAES) of a tolerance of its own tool-model twin, so each `DISAGREE` comes from the effect the control exists to show. No control is `AGREE`. PC-P is `NOT_COMPARABLE(capability)` in both tools and propagates nothing (§17.3(c)). Both tools' pairs count |
| 3 | X31's reference clause: §2.3 step 5 as replaced by §17.5 (RC1–RC4) | **NOT MET.** RC1 and RC2: row 5, two references. RC3: row 6, one reference (IDAES; DWSIM absent). RC4: row 7, no reference. 2 of 4 cases have two references (target 4). This is §18.6's branch B-i. Its pre-registered outcome is "not met", because IDAES qualified RC3 but not RC4 |
| 4 | Inverse kinds, reported per §17.5 outside the count (Q-S03-5, Frank: "All three") | **All three kinds compared.** Purity (RC5): row 5, two references. Recovery (RC6): row 5, two references. Temperature (RC7): row 6, one reference (IDAES). DWSIM cannot express a temperature specification on an interior stage |
| 5 | D19, column part (§7.5). Minimum evidence: "matched-model inputs, independence disclosure and verdicts" | **MET for the states S03 covers, with a recorded gap.** The matched-model inputs are recorded per pair and re-checked on the solved state by rule 2c (§5.1). The disclosure is §5.2. The column is numerically verified against two independent implementations at 9 registered states and against one at 5. It has no independent verification at the 3 states of the RC4 family, the refluxed absorber (§5.3) |
| 6 | Perturbation study (§3.2, §7.4): reported, not classified | **Reported.** 8 of the 10 perturbed cases are compared: 5 by both tools and 3 by IDAES alone. Neither tool compares RC4-D or RC4-z. Each compared finite-difference response matches ours to within 0.0068 of its bound `tol(y_pert) + tol(y_base)`, while the twin's response is at least 4209 bounds. No sensitivity capability is claimed |
| 7 | A17 (§11): this document exists, is the `verdict` agent's, and records §7.5's items | **Met once this file is committed.** The manifest at `959131dc` still records A17 as failed. Regenerating it is the build lane's task |

Status lines. None of these is a verdict item, and none changes a verdict above.

| Item | Status |
| --- | --- |
| B2b-1 and the session decision: `bound_mult_init_method` goes through Ipopt's options file, and §18.1's contingency is not applied | **I concur, on procedure** (§1.4). The `reviewer`'s confirmation is still pending. If the reviewer reverses it, verdicts 1, 3, 4 and 5 reopen for six IDAES pairs (§1.6) |
| A10 on CI: the live-solve comparison differs by 3.4e-12 relative against a 1e-12 test | **Open, for the reviewer; not ruled here.** One fact for the reviewer: the classified ratio nearest the boundary is 1.10 (PC-LI `top[A]`). A last-bit change cannot move any classification |
| The harvest step | Open, for the reviewer. Not examined here |
| ruff E501 in the tool scripts (§13) | Open, for the reviewer. Not examined here |
| `scripts/gate.sh`, and CI green on both architectures (§13) | Not run. The manifest marks both `unsupported`. Both are required before the merge |

---

## 0. The evidence judged, and its provenance

These verdicts apply to the bytes below. They do not transfer to other records.

| Record | Produced by, where | SHA-256 |
| --- | --- | --- |
| DWSIM: 11 standing records (RC1, RC1-RR, RC1-BR, RC1-z, RC2, RC2-RR, RC2-B, RC2-z, RC5, PC-P, PC-L) | WO-S03-3, a blind run, commit `95870140`, `.venv-dwsim` (DWSIM 9.0.5, pythonnet 3.1.0, .NET 8) | each listed in `SHA256SUMS` |
| DWSIM top-up: RC3, RC3-Q, RC3-z, RC4, RC4-D, RC4-z, RC6, RC7 | WO-S03-3b, `5474531f`. Then `65e3a786` changes one line of `qualification/dwsim.json`: it writes in the commit id `5474531f` where a placeholder stood. That is before any comparison | `qualification/dwsim.json` `2ac3bb97…b400` |
| IDAES: 20 records | WO-S03-2b, `2eb71ac0`, `.venv-idaes` (idaes-pse 2.13.0, extensions 3.4.2, Ipopt 3.13.2 with MUMPS). They supersede `6d9486a0`, whose 20 P0 attempts the new run reproduces exactly | `qualification/idaes.json` `bd5df292…917b` |
| Our side: 18 records | `scripts/s03_references_ours.py`, regenerated at `c76bf1c7`. Only `cases_sha256` changed | each listed in `SHA256SUMS` |
| Cases and twin | `docs/derivations/scripts/s03_cases.json`; `s03_reference.json` (4577 claims, `--check` passing in the manifest) | `c901d6c9…3f39`; `95ef9bd2…0c67` |
| Comparison | `scripts/s03_reference_comparison.py --write` at `959131dc` | `comparison.json` `5c7d139c…585d`; `SHA256SUMS` `fb65ba28…6f70` |

**What I checked, and how.**
- **Hashes.** All 60 entries of `SHA256SUMS` match the files at `5a06e53c`.
- **Order (§2.3 step 3).** The qualification commits (`95870140`, `5474531f`, `2eb71ac0`) all come before the classifier's first run
  (`12b50f48`). From `2eb71ac0` to `5a06e53c`, `git diff` touches no tool record. It touches only the 18 `ours-*` files, each on its
  `cases_sha256` line.
- **The classifier change after the first run** (B4-11, `959131dc`). I diffed the two documents. It changed nine floats, all DWSIM
  rule 2 energy balances of order 1e-12 W, against a 1e-3 W threshold. No label, ratio, tolerance, X31 field or control field changed.
- **Fingerprints.** All DWSIM records carry one fingerprint, and all IDAES records carry one. Each equals
  `docs/reference-environments.md` §3, so no pair is rule 1.
- **Independent recomputation.** I wrote a scratch script that imports nothing from the repository and kept it out of the commit. It reads each
  tool record's registered quantities, our records and the twin's 25-digit values. It evaluates §6's tolerance in 50-digit decimal,
  then applies rule 3, rule 4, §17.3 and §17.5's table.
  - *Result.* The same label for 40 of 40 pairs. For every rule-4 pair, the same worst quantity, the same worst ratio (to 1e-9
    relative) and the same count of quantities outside. The same §17.5 rows and the same clause.
  - *What the agreement checks.* The classifier reads the records' raw fields (B4-2). My script reads the scripts' summaries.
    The agreement therefore also cross-checks the two layers of each record.
  - *What it does not check.* My script takes rule 0 availability as recorded. I checked that against the attempt lists for a
    sample: DWSIM RC1, RC1-BR and RC6, and IDAES RC3 and RC4.
- **Re-runs of the committed checks** (read-only).
  - `scripts/s03_reference_comparison.py --check`: exit 0.
  - `pytest tests/test_s03_references.py tests/test_s03_ours.py`: 290 passed in 228 s on this x86-64 workstation. That includes
    A10 against a live solve of our side, and A11, A12 and A14.

**Provenance notes.** None moves a classification.
- **N1.** WO-S03-2's IDAES pilot runs (B2-4) kept no log. `pilot_runs` records them as "no log retained". §18.2 requires disclosure,
  not prevention, and blindness stays procedural (§2.1).
- **N2.** Some `NOT_COMPARABLE(capability)` labels name convergence or accuracy failures, not a missing feature. They are DWSIM's
  RC3 family, RC1-BR and PC-P, and IDAES's L3 attempts on the RC4 family and PC-P. That is the registered label (§2.3 step 4,
  rule 0, §17.5 "absent"), but wherever the label is cited, its reason must be quoted with it (§8 item 6).

## 1. Verdict 1: the pair classifications

### 1.1 Criteria as registered

- *Tolerance.* §6: `|ours − tool| ≤ a_k + 1e-6 |v_twin|`, with a_flow 3.1e-7 mol/s, a_T 1e-5 K and a_duty 1e-2 W.
- *Rule order.* §7.1: rules 0, 1, 2, 2b (IDAES only), 2c, 2d, 3, 4.
  - Rule 2d uses §17.4's thresholds per kind, and IDAES's path dependence (§18.4).
  - Rule 2d can produce only `NOT_COMPARABLE`, never a pass.
- *Controls.* §17.3, as amended for IDAES by §18.3.
- *Limits on this verdict.* The `verdict` agent may not change a tolerance, a setting, a mapping, a level or a case (§7.5).

### 1.2 Per (case, tool)

| Case | DWSIM: classification, (level, method, tolerance), worst quantity (ratio) | IDAES: classification, (level, position), worst quantity (ratio) |
| --- | --- | --- |
| RC1 | **AGREE**, (L1, Wang–Henke, 1e-8), `top[B]` 0.0326 | **AGREE**, (L3, P0), `Q_reboiler` 4.6e-4 |
| RC2 | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `bottom[A]` 3.3e-8 | **AGREE**, (L2, P0), `Q_condenser` 7.1e-4 |
| RC3 | absent. Napthali–Sandholm hits its 1000-iteration limit at every tolerance. Wang–Henke fails DWSIM's own balance check at 1e-10 to 1e-8, and rule 2's 3.1e-8 mol/s balance at 1e-7 and 1e-6 | **AGREE**, (L3, P1), `L[5]` 5.1e-3 |
| RC4 | absent. L1: a full-reflux condenser has no native rate for the vapour distillate D = V₁ under either method. L2(a): DWSIM error (Napthali–Sandholm), convergence error (Wang–Henke) | absent. L1 and L2: `TrayColumn` always builds a reboiler. L3: P0, P1 and P2 each end at 500 iterations |
| RC5 | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `L[1]` 0.0179 | **AGREE**, (L3, P1), `Q_reboiler` 4.4e-4 |
| RC6 | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `bottom[A]` 0.0202 | **AGREE**, (L2, P1), `bottom[A]` 0.0202 |
| RC7 | absent, by structure. DWSIM's reboiler temperature specification is stage 7's, and `StageNumber` selects no stage. Napthali–Sandholm's reflux ratio is not L₁/V₁ (§17.2 F2) | **AGREE**, (L3, P0), `Q_condenser` 4.7e-4 |
| RC1-RR | **AGREE**, (L1, Wang–Henke, 1e-8), `top[B]` 0.0380 | **AGREE**, (L3, P0), `Q_reboiler` 4.6e-4 |
| RC1-BR | absent. At (Wang–Henke, 1e-8) the accuracy rerun moved 0.1006 tolerance, against rule 2d's 0.1. Every other rung fails rule 2 or 2d | **AGREE**, (L3, P0), `Q_reboiler` 4.6e-4 |
| RC1-z | **AGREE**, (L1, Wang–Henke, 1e-8), `top[B]` 0.0180 | **AGREE**, (L3, P0), `Q_reboiler` 4.5e-4 |
| RC2-RR | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `bottom[A]` 3.8e-8 | **AGREE**, (L2, P1), `Q_condenser` 7.1e-4 |
| RC2-B | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `bottom[A]` 2.9e-8 | **AGREE**, (L2, P0), `Q_condenser` 7.2e-4 |
| RC2-z | **AGREE**, (L1, Napthali–Sandholm, 1e-10), `bottom[A]` 7.9e-9 | **AGREE**, (L2, P0), `Q_condenser` 6.6e-4 |
| RC3-Q, RC3-z | absent, as RC3 | **AGREE**, (L3, P1): `L[5]` 6.6e-3 and 5.1e-3 |
| RC4-D, RC4-z | absent, as RC4 | absent, as RC4 |
| PC-P | absent. Rule 2 at every rung. L2(a) is unavailable, because the reflux-ratio specification occupies the condenser slot | absent. L1 and L2: IDAES's partial `Condenser` is not S02's. L3: P0, P1 and P2 each end at 500 iterations |
| PC-L | **DISAGREE** (required), (L1, Wang–Henke, 1e-8), `Q_reboiler` 243.289 | `not_applicable` (registered absence) |
| PC-LI | `not_applicable` (registered absence) | **DISAGREE** (required), (L3, P0), `Q_reboiler` 243.292 |

**Reason for every `AGREE`.** Rules 0 to 3 do not fire, and every registered quantity lies within §6's tolerance.
- *Rule 2.*
  - DWSIM's own component balance closes to ≤ 1.59e-8 mol/s (RC1-RR) against 3.1e-8, and its energy balance to ≤ 1.6e-6 W
    against 1e-3.
  - IDAES closes to ≤ 1.7e-10 mol/s and ≤ 1.15e-4 W.
  - Every final solve that decides ended "Optimal Solution Found".
- *Rule 2b.* The largest SmoothVLE shift is 5.00003e-9 K, against 1e-7 K. That is ε/2, §18.1's signature of a state block at a
  saturation kink. Every block carries the registered ε.
- *Rule 2c.* Stage counts, maps and feed stages match. Every pressure deviation and every intermediate duty is 0. The largest
  relative miss of a specification definition is 8.5e-10, against 1e-4.
- *Rule 2d.*
  - Specification residuals: DWSIM ≤ 8.5 % of the kind's threshold (RC1-RR, Wang–Henke at 1e-8); IDAES ≤ 1.5e-4 of it.
  - Rerun movement: DWSIM ≤ 0.0931 tolerance (RC1-z); IDAES ≤ 0.00694 (RC1).
  - IDAES path dependence: ≤ 7.75e-5 (RC5).
- *Rule 3.* Our side is within 0.0202 of a tolerance of the twin on every case (RC6 `bottom[A]`), and within 3.5e-3 on every case
  except RC6.

**The third corner.** Every tool value in an `AGREE` pair also lies within 0.0380 of a tolerance of the twin (DWSIM, RC1-RR
`top[B]`); IDAES's lie within 6.3e-3 (RC3-Q). Ours, the tool and the twin agree pairwise. No `AGREE` rests on two corners alone.

**Margin, reported, not used.** The largest ratio in any counted pair is 0.0380 (DWSIM RC1-RR `top[B]`), so every `AGREE` would
survive a tolerance 26 times tighter. One margin is thin. DWSIM's RC1 family runs at (Wang–Henke, 1e-8):
- its reruns moved 0.071–0.093 tolerance, inside rule 2d's 0.1 by factors of 1.07 to 1.4;
- RC1-BR missed the 0.1 by 0.6 % and is absent;
- the comparison ratios there (0.018–0.038) are of the same order as the tool's own sensitivity to its tolerance.

These `AGREE`s are admissible under the registered rule, and IDAES agrees on the same states to ≤ 4.6e-4. But DWSIM's evidence on
the RC1 family sits near its accuracy floor. That is a limitation that travels (§8 item 4).

### 1.3 The rulings that set the tool paths: when each was fixed, and whether it is tuning

No comparison existed before `12b50f48`. Each ruling below is dated against that.

| Ruling | Fixed | Tuning? |
| --- | --- | --- |
| DWSIM's ladder: Napthali–Sandholm, then Wang–Henke, at each tolerance 1e-10 … 1e-6 (§17.2) | Amendment 1, after WO-S03-3's blind qualification and before any comparison | **Not tuning; post hoc with respect to convergence, and disclosed.** It is uniform, it is derived from DWSIM's source (F1–F3), and its author had seen no tool quantity. It removed rungs that never existed. It added Wang–Henke attempts that only the RC3 and RC4 families lacked, and those still did not qualify. Eight of DWSIM's nine `AGREE`s come from the eleven standing records, which are unchanged (§17.8). The ninth, RC6, was qualified in the top-up at (L1, Napthali–Sandholm, 1e-10). That is the first position under the original §5.2 ladder too, so the amendment did not select it |
| IDAES's path ladder P0/P1/P2 on B2-4's common start (§18.1, §18.2) | Amendment 2, after WO-S03-2's first qualification (`6d9486a0`) and before any comparison | **Not tuning; post hoc with respect to convergence, and disclosed.** It is uniform and closed at three positions. ε, the tolerances and the convergence test are unchanged. P0 reproduces `6d9486a0` in 20 of 20 attempts. Wherever two positions converged, they agree to ≤ 7.75e-5 tolerance (§18.4), so the position chosen does not steer the answer. Six selections moved to P1: RC3, RC3-Q, RC3-z and RC5 at L3; RC2-RR and RC6 at L2 |
| B2b-1: the input route for `bound_mult_init_method` | Build lane, WO-S03-2b, before the recorded run | §1.4 |
| PC-LI (§18.3) | Amendment 2, before WO-S03-2b | **Not chosen by convergence.** Its configuration and its size are inherited from PC-L: `P_r v_i` = 10 J/mol, fixed by SYN-001. It `DISAGREE`s at the registered discrimination (243.292) and reproduces its tool model to 4.6e-4, so the override was applied and the harness resolved the effect |

**Corroboration.** DWSIM's inputs were fixed before Amendment 2. DWSIM independently `AGREE`s on three of the six states IDAES
reached through P1: RC2-RR, RC5 and RC6. The RC3 family's P1 selections have no second tool behind them. Without P1, RC3 would be
row 7 rather than row 6. X31's clause would still be "not met", because RC4 is row 7 in both readings.

### 1.4 B2b-1: my reading of §18.1's contingency

**The registered text.** §18.1: "if Ipopt rejects `bound_mult_init_method`, P1 and P2 run without it, and the record says so. No
other option is substituted."

**The record** (`qualification/idaes.json` → `warm_start_options_check`):
- the `ipopt` executable's command-line (AMPL keyword) interface refuses the keyword;
- through Ipopt's options file, Ipopt accepts it, and an invalid value raises `OPTION_INVALID`, so Ipopt parses and validates it;
- every P1 and P2 solve lists `OF_bound_mult_init_method: mu-based` (checked on `results/idaes-RC3.json`).

**Reading.**
- The ladder registers an option set and its values. It does not register an input route.
- The solver accepted the registered option with the registered value, so no option was substituted.
- Applying the contingency would have run a path other than the registered P1 while the registered one could be executed.

I concur with the session decision. This is a procedural reading, not a numerical result. Confirming it remains the `reviewer`'s
task (§18.8: the review checks "that the positions are as registered").

### 1.5 Alternatives rejected

- **Admit DWSIM's RC1-BR at a rerun of 0.1006, "within rounding of 0.1".** Rejected. A failed criterion stays failed.
- **Count IDAES's "Solved To Acceptable Level" iterates.** Rejected: ADR 0014 D7, §18.1. Today this is moot, because P1
  qualified those cases. If B2b-1 is reversed, the rejection still binds.
- **Treat IDAES's P1 selections as tuning and discount them.** Rejected. The ladder was registered before WO-S03-2b and before any
  comparison, closed and uniform, and P0 was reproduced. Path dependence shows the positions change the path, not the answer
  (§1.3).
- **Treat a missing control on a configuration as voiding that configuration's pairs** (DWSIM's Napthali–Sandholm route; IDAES's L2
  `TrayColumn` route and its no-condenser L3 route). Rejected. §17.3 makes controls per tool, not per configuration, and its
  point 2 considered and accepted exactly this.
- **A tighter verdict tolerance "because the margins allow it".** Rejected. The `verdict` agent may not change a tolerance.

### 1.6 What would change it

- The `reviewer` reverses B2b-1. Then the P1 and P2 records do not run the registered path. §18.1's harness-defect clause requires
  correcting the harness and repeating the run, and these pairs reopen: IDAES RC3, RC3-Q, RC3-z, RC5, RC6 and RC2-RR.
- A record shown to have read our results, the twin or a comparison output (A03).
- A re-run of `spikes/references/s03_qualify.sh` that does not reproduce the committed records. Or a fingerprint mismatch.
- A cross-architecture difference that changes a label or a §17.5 row, not only last bits.
- A change of SYN-001's definition, a mapping, a tolerance, a tool version or a setting. Each requires re-qualification and a new
  verdict.

## 2. Verdict 2: the positive controls

**Criteria as registered.**
- (a) A control that classifies `AGREE` stops the comparison.
- (b) A tool's pairs count only if at least one of its registered controls classifies `DISAGREE`.
- (c) A `NOT_COMPARABLE` control propagates nothing by itself.
- (d) (PC-L, IDAES) and (PC-LI, DWSIM) are `not_applicable`.

DWSIM's controls are PC-P and PC-L. IDAES's are PC-P and PC-LI (§17.3, §18.3).

| Control | Classification | Max ratio (quantity), outside | Registered discrimination | Distance to the tool-model twin |
| --- | --- | --- | --- | --- |
| (PC-L, DWSIM) | `DISAGREE` | 243.289 (`Q_reboiler`), 22/29 | 243.292, 22/29 | 0.0326 (`top[B]`) |
| (PC-LI, IDAES) | `DISAGREE` | 243.292 (`Q_reboiler`), 22/29 | 243.292, 22/29 | 4.6e-4 (`Q_reboiler`) |
| (PC-P, DWSIM) | `NOT_COMPARABLE(capability)` | — | 176.357 | none: no tool values |
| (PC-P, IDAES) | `NOT_COMPARABLE(capability)` | — | 176.357 | none: no tool values |

**The marginal quantities.** On temperatures the controls are marginal, exactly as registered:
- PC-L: `T[4]`–`T[7]` are at 0.60–0.79 of a tolerance (§3.3 predicted 0.59–0.78);
- PC-LI: 0.58–0.78 (§18.3: 0.585–0.782);
- the outside quantity closest to the boundary is `top[A]`, at 1.12 and 1.10.

The duties and flows carry both controls, and neither result depends on one quantity.

**Why PC-P is absent.**
- *DWSIM.* Rule 2 fails at every rung, L2(a) is unavailable and L3 is inadmissible.
- *IDAES.* At L1 and L2 the partial condenser cannot be expressed. At L3, every position ends at 500 iterations.

Under (c), that propagates nothing. No control is `AGREE`, and each tool has a `DISAGREE` control, so no pair is relabelled.

**What the controls do not show.**
- *Each control covers one harness route.* DWSIM's: a full-reflux condenser under Wang–Henke at 1e-8. IDAES's: the L3 composition
  at RC1. No control ran on DWSIM's Napthali–Sandholm route (the RC2 family, RC5, RC6), on IDAES's L2 `TrayColumn` route (the RC2
  family, RC6), or on IDAES's no-condenser L3 route (the RC3 family).
  - The registered criterion accepts this (§17.3 point 2).
  - What guards those routes is rule 2c's per-record semantic checks, A03's blindness, and the discriminations of §3.2 (≥ 8382
    tolerances per perturbation) and E1 (1.07e6 for a feed one stage off).
- *The tools' missing Poynting factor is not shown at column level.* PC-P failed in both tools. That rests on T06's PC-2 (a flash)
  and on §3's identity at `P_r` (§17.11, §18.9).

## 3. Verdict 3: X31's reference clause

**Criteria as registered.**
- The count covers RC1–RC4 (§2.3 step 5).
- §17.5's classes, rows and clause, which the `verdict` agent applies as written.
- §18.6 pre-registers the outcomes by branch.

| Case | DWSIM | IDAES | §17.5 row | Outcome |
| --- | --- | --- | --- | --- |
| RC1 | comparable, `AGREE` | comparable, `AGREE` | 5 | two references |
| RC2 | comparable, `AGREE` | comparable, `AGREE` | 5 | two references |
| RC3 | absent | comparable, `AGREE` (L3, P1) | 6 | one reference (IDAES) |
| RC4 | absent | absent | 7 | no reference: not met |
| **X31 reference clause** | | | | **not met**: 2 of 4 cases with two references (target 4) |

**RC3, DWSIM absent** (row 6, the absent tool and its reason quoted, as §17.5 requires):
- L1, Napthali–Sandholm: no tolerance passed rules 2–2d ("Solver reached the maximum number of iterations without converging").
- L1, Wang–Henke: DWSIM's own mass-balance check failed at 1e-10, 1e-9 and 1e-8, and rule 2's tool-internal balance failed at
  1e-7 and 1e-6.
- L3: not admissible for DWSIM (§2.2).

**Row 7, in §17.5's prescribed words.** "X31 reference clause: not met for RC4: no independent reference expresses it."
- *IDAES.* `TrayColumn` always builds a condenser and a kettle reboiler, so L1 and L2 cannot express RC4's `none` reboiler end. At
  L3, each registered position ended at 500 iterations: P0, P1, and P2, whose first continuation step ended locally infeasible.
  The initializer's full solve also reached its iteration limit.
- *DWSIM.* At L1, a full-reflux condenser has no native vapour-distillate rate (D = V₁) under either method: the native rate is the
  liquid distillate. At L2(a), a partial condenser with its liquid distillate fixed at 0 ended in a DWSIM error under
  Napthali–Sandholm and a convergence error under Wang–Henke. L3 is not admissible (§2.2).

**The branch.**
- §18.6 branch B-i occurred: PC-LI is `DISAGREE`, and no control is `AGREE`.
- Its pre-registered mapping: "met where available, 2 of 4 cases with two references, if and only if IDAES qualifies both RC3 and
  RC4. Otherwise not met."
- IDAES qualified RC3 and not RC4. The outcome is the pre-registered one.
- Per §17.5:
  - no case changes;
  - no tool is added within S03;
  - no tolerance moves;
  - the manifest may still be `tested`.
- Whether R01 or a release accepts the clause unmet is outside S03.

**Frank's Q-A2-4 decision** (plan a third reference tool, S09). On these verdicts, S09's cases are:
- the RC4 family, which has no reference and is the only case that fails the clause;
- the RC3 family, RC7 and RC1-BR, which have one reference each.

§17.5's table is written for two tools. A third reference can change X31's verdict only under a rule that S09's own specification
registers. Under S03's rule as written, nothing outside S03 changes S03's clause outcome.

**Alternatives rejected.**
- **Read "where available" as excusing a case for which no tool is available.** Rejected. The original §2.3 step 5 already required
  at least one available tool for every case, and §17.5 row 7 is explicit.
- **Count the twin as a reference for RC4.** Rejected. The twin shares SYN-001's closed forms and S02's definitions with our
  implementation, so it is not independent (§2.1).
- **Re-qualify RC4 with an initializer variant, or with another DWSIM unit.** Rejected: §18.1 ("An initializer variant for the RC4
  family"), §17.2 ("Not added"), §2.2 (no DWSIM L3). Either would be a search for a passing setting after the failure was seen.

**What would change it.**
- The `reviewer` finds a harness defect in IDAES's RC4 L3 build or in DWSIM's RC4 L2(a) build: a path or a connection other than
  the registered one. §18.1 then requires correcting the harness and repeating the run. If RC4 then qualified in one tool with
  `AGREE`, it would be row 6, and the clause would be "met where available, 2 of 4".
- A structural fact shown to be wrong, for example a native D = V₁ specification in DWSIM that the inspection missed. Then RC4 is
  re-qualified, by amendment.
- B2b-1 reversed (§1.6). That could move RC3 to row 7, and the clause would stay "not met".

## 4. Verdict 4: the inverse kinds (outside the count)

| Kind | Case | DWSIM | IDAES | Row | Outcome |
| --- | --- | --- | --- | --- | --- |
| purity | RC5 | `AGREE`, (L1, Napthali–Sandholm, 1e-10) | `AGREE`, (L3, P1) | 5 | two references |
| recovery | RC6 | `AGREE`, (L1, Napthali–Sandholm, 1e-10) | `AGREE`, (L2, P1) | 5 | two references |
| temperature | RC7 | absent (structural, §1.2) | `AGREE`, (L3, P0) | 6 | one reference (IDAES) |

- **RC5 and RC6.** Rule 2c reads each specification from the tool's own flows:
  - RC5, DWSIM's molar `Component_Fraction` of A on the full-reflux condenser: purity in the vapour distillate within 3.2e-15
    (threshold 1e-8 absolute);
  - RC6, DWSIM's `Component_Recovery` of C, 99 % converted to 0.99: recovery exactly 0.99;
  - RC5 and RC6 in IDAES, the L2(b) equations of S06 §2: residuals ≤ 1.5e-12.

  §17.1's partner claim shows that a dropped inverse specification would miss by ≥ 31543 tolerances.
- **RC6 is the most ill-conditioned state** (σ_min 6.06e-4).
  - Both tools land close to the twin: DWSIM within 8.9e-9 of a tolerance, IDAES within 5.4e-4.
  - Our side is the least accurate of the three: 0.0202 tolerance on `bottom[A]`. That is inside rule 3's 0.1 by a factor of 5.
    It is 2.4 times the S02 floor that §6 and A06 quote (8.5e-3), which is a reference value and not a criterion.
  - IDAES's P0 at L2 converged, but its rerun moved 0.340 tolerance (rule 2d). So P0 was excluded, and P1 was selected by the
    registered order (rerun 0). P0's final solve agrees with P1 and P2 to 1.8e-6.
- **RC7.** The temperature residual is 0 relative (threshold 1e-9), and the reflux ratio's is 2.2e-15. Our stage 6 maps to IDAES's
  `fs.stage6` at L3. §17.4's wrong-stage readings miss by 1.45–2.08 %, which is ≥ 145 times rule 2c's threshold, so a stage
  mix-up would have been `NOT_COMPARABLE(semantics)`, not `AGREE`.
- **Q-S03-5 ("All three"): delivered.** Each kind is compared against at least one independent reference, and temperature against
  exactly one (§17.11 expected this).

## 5. Verdict 5: D19, column part

### 5.1 Matched-model inputs

§5.1 rows 1–15, with §17.4 and §18.2, are recorded per pair in each record's structural inspection (Q-X1–Q-X9). Rule 2c re-checks
them on the solved state (§1.2).

| Cases | DWSIM | IDAES |
| --- | --- | --- |
| RC1, RC1-RR, RC1-z, PC-L (PC-LI for IDAES) | `DistillationColumn` with a `Full_Reflux` condenser (vapour distillate, all liquid refluxed), Wang–Henke's `Stream_Ratio` = L₁/V₁, and reboiler `Stream_Ratio` = BR | L3: `Tray` units, a `Flash` as the partial condenser, `Reboiler`, joined by `Arc`s. RR as the L2(b) equation `L₁ − RR*·V₁ = 0`; BR native |
| RC2, RC2-RR, RC2-B, RC2-z | `Total_Condenser`, subcooling 0 K. Napthali–Sandholm's `Stream_Ratio` = Σr/D. Bottoms `Product_Molar_Flow_Rate` = B | L2: `TrayColumn` with a total condenser. RR native (reflux over distillate); B as the L2(b) equation `L_N − B* = 0` |
| RC3 family | — | L3: no condenser, the `top` inlet on stage 1, reboiler duty native |
| RC5 | `Full_Reflux`; molar `Component_Fraction` 0.85 of A on the condenser; BR | L3; purity as the L2(b) equation of S06 §2 |
| RC6 | `Total_Condenser`, RR 1.5; reboiler `Component_Recovery` 99 % of C | L2; recovery as the L2(b) equation `n_C − 0.297 = 0` on the bottoms |
| RC7 | — | L3; `T_6 − 368 = 0` on our stage 6 |

**SYN-001 in each tool.** Each tool runs SYN-001 through T06's definitions (§5.1 row 1). Every pressure is `P_r` = 1e5 Pa
exactly, and every recorded deviation is 0 Pa.

### 5.2 Independence disclosure

> A comparison verifies a second, independent implementation of the same equations. It is numerical verification, not empirical
> validation. (§2.1)

- **Shared elements.** All four corners — ours, the twin, DWSIM and IDAES — share SYN-001's definition, entered in the tools through
  T06's definitions. The column semantics of §5 are matched by construction. An error common to that definition cannot be seen here.
- **The twin is not independent.** It is the third corner: it shares SYN-001's closed forms and S02's and S06's definitions with
  our implementation.
- **Blindness is procedural.** A03 passes on every qualification commit. The tool scripts were written by this project's build
  lane, which knows the project. WO-S03-2's IDAES pilot runs kept no log (N1).
- **Post hoc paths, disclosed.**
  - DWSIM's ladder was amended after its first blind qualification and before any comparison (§17.2).
  - IDAES's path ladder was registered after its first blind qualification and before any comparison (§18.1). Six IDAES
    selections are at P1.
  - B2b-1 passes one warm-start option through Ipopt's options file (§1.4).
- **What an L3 `AGREE` verifies.** It verifies our column against IDAES's `Tray`, `Flash` and `Reboiler` equations as the harness
  connected them (§14).
- **IDAES's smoothing.** IDAES agrees at ε = 1e-8 K: SmoothVLE's sharp limit, to within ε (§14).

### 5.3 The verdicts, and D19's question: is the column verified?

**Two independent references** (DWSIM and IDAES, both `AGREE`), 9 states:
- RC1, RC1-RR and RC1-z;
- RC2, RC2-RR, RC2-B and RC2-z;
- RC5 (purity) and RC6 (recovery).

**One reference** (IDAES), 5 states: RC3, RC3-Q and RC3-z (the stripper); RC7 (temperature); RC1-BR.

**No independent reference**, 3 states: RC4, RC4-D and RC4-z (the refluxed absorber). Our side meets the twin there (rule 3,
within 0.1 tolerance), and the twin is not independent.

**Against §18.6's pre-registered D19 for branch B-i.**
- *Two references expected:* RC1, RC1-RR, RC1-z, RC2, RC2-B and RC2-z. Measured: all six have two.
- *One reference expected:*
  - RC7 and RC1-BR (IDAES): measured one each, as expected;
  - RC2-RR, RC5 and RC6 (DWSIM) "unless IDAES now qualifies them": IDAES now qualifies them, so they have two.
- *The RC3 family* is IDAES-only.

**My answer.**
- **Two independent implementations.** Within the supported scope — SYN-001 only, every pressure `P_r`, the registered states — our
  column is numerically verified against two independent implementations for the conventional column: partial or total condenser,
  kettle reboiler, liquid feed, under ratio, rate, purity and recovery specifications.
- **One implementation (IDAES).** It is verified against one for the stripper: no condenser, a liquid `top` inlet and a
  duty-specified reboiler. Also for an interior stage's temperature specification, and for one boil-up perturbation of the
  conventional column.
- **None.** It is not independently verified for the refluxed absorber: no reboiler, a vapour `bottom` inlet, and a vapour
  distillate rate. That topology rests on the design-lane twin alone.

S01's cascade is exercised on every RC state (§10.3). Its `none` reboiler end with a vapour `bottom` inlet, which only RC4 has, has
no independent check.

**D19's minimum evidence for S03's part is present:** matched-model inputs (§5.1), the disclosure (§5.2) and these verdicts. D19 as
a requirement also spans T06 and R01. This verdict covers only S03's column part.

## 6. Verdict 6: the perturbation study (reported, not classified)

The full table, Δy per quantity for ours, each tool and the twin with its bound, is `comparison.json` → `perturbation_response`,
at the SHA-256 in §0. Its summary:

| Perturbed case | Twin's response: max \|Δy\| / bound (quantity) | DWSIM: max \|Δy_tool − Δy_ours\| / bound | IDAES: the same |
| --- | --- | --- | --- |
| RC1-RR | 4209 (`L[1]`) | 0.0026 | 5.0e-6 |
| RC1-BR | 5183 (`Q_reboiler`) | — (RC1-BR absent) | 1.1e-5 |
| RC1-z | 19430 (`top[B]`) | 0.0068 | 3.1e-5 |
| RC2-RR | 6806 (`reflux`) | 2.6e-9 | 5.2e-6 |
| RC2-B | 10880 (`top[B]`) | 2.2e-9 | 1.7e-5 |
| RC2-z | 19030 (`top[B]`) | 1.3e-8 | 2.6e-5 |
| RC3-Q | 16170 (`L[5]`) | — | 1.3e-3 |
| RC3-z | 16670 (`top[A]`) | — | 9.0e-4 |
| RC4-D | 8111 (`L[2]`) | — | — |
| RC4-z | 14050 (`top[A]`) | — | — |

The bound is `tol(y_pert) + tol(y_base)`, so the twin's ratios are about half of §3.2's (§3.2 divides by `tol(y_pert)` alone).
Where both points are `AGREE`, each response matches ours by construction. The measured mismatch is at most 0.0068 of the bound.
The responses cover only registered neighbouring states. They verify no derivative, and they are no sensitivity capability (§14).

## 7. Separate findings

- **F-1 (registered text; the decision is unaffected).** §17.8 condition 2 says every `tool_settings` key of the earlier cases file
  must be "present, and equal" in the current file. Read literally, that fails at `95870140`: Amendment 1 added
  `column_method_order_amendment_1` inside `tool_settings.DWSIM`.
  - §17.8 itself states that the three conditions hold for the eleven standing records "by construction, since the change is
    additions only", and §18.5 repeats that they stand.
  - B4-9's reading — every earlier value present and identical, and a mapping may gain keys — is the one under which §17.8 is
    consistent with itself.
  - I verified that this reading holds at all four qualification commits (`95870140`, `5474531f`, `6d9486a0`, `2eb71ac0`). Every
    earlier value is present and identical, and no case entry changed.
  - I decide under §17.8 as written, its declaration included: the eleven records stand.
  - The next amendment should correct the wording of condition 2.
- **F-2 (registered behaviour, for information).** Rule 2d's rerun says nothing new whenever Ipopt's last step satisfies both the
  registered and the looser tolerances at once. 8 of the 15 selected IDAES records rerun bit-identically (movement 0.0).
  - This is permitted: rule 2d can only exclude, and an inaccuracy would surface as a `DISAGREE` (§7.1).
  - For IDAES, the checks that do discriminate are §18.4's path dependence (≤ 7.75e-5) and the tool's distance to the twin
    (≤ 6.3e-3).
  - RC6's P0 (0.340) shows that the rerun does fire on an ill-conditioned root.
  - No action for S03. A later reference specification that wants rule 2d to discriminate for Ipopt would need a rerun that changes
    where the solver stops.
- **F-3 (wording that travels).** `NOT_COMPARABLE(capability)` covers structural absences (DWSIM RC4 at L1, RC7; IDAES RC4 at
  L1/L2), convergence failures (DWSIM RC3 family; IDAES RC4 at L3; PC-P) and an accuracy failure (DWSIM RC1-BR, rerun 0.1006). A
  release report must quote the reason, not only the label.
- **F-4 (B4-4, moot).** Under §17.3(b), "every pair of that tool" is read as the pairs that reached rule 2 or beyond. Both tools have
  a `DISAGREE` control, so it relabels nothing here. I make no ruling. A re-run in which a tool loses both controls would need one.

## 8. Limitations that must travel into the manifest and the release report

1. **Evidence class.** These comparisons are numerical verification against independent implementations of the same synthetic
   equations. They are not empirical validation, not optimality evidence and not a sensitivity capability. Package status:
   `implemented`; `tested` once A17 is regenerated, the reviewer's open items are closed, and the gate and CI pass. Not `reviewed`,
   not `released`.
2. **X31's reference clause is not met.** The refluxed absorber (the RC4 family) has no independent reference. RC3 counts with one
   reference, IDAES. Only 2 of 4 counted cases have two references.
3. **Post hoc tool paths.**
   - DWSIM's ladder amendment (§17.2) and IDAES's path ladder (§18.1) were both ruled after a first blind qualification and before
     any comparison.
   - Six IDAES selections are at P1 (RC3, RC3-Q, RC3-z, RC5, RC2-RR, RC6).
   - B2b-1's options-file route awaits the reviewer's confirmation.
4. **DWSIM's RC1 family sits near its accuracy floor.** It runs at (Wang–Henke, 1e-8), with reruns of 0.071–0.093 against rule 2d's
   0.1. RC1-BR is excluded at 0.1006, and that stays failed.
5. **Each control covers one configuration.** PC-L is at RC1 under Wang–Henke; PC-LI is on RC1's L3 composition. No control ran on
   DWSIM's Napthali–Sandholm route or on IDAES's L2 `TrayColumn` and no-condenser routes. PC-P failed in both tools, so neither
   tool's missing Poynting factor is shown at column level, and our Poynting terms stay without an independent check (§14, §17.11,
   §18.9).
6. **"Capability" absences include convergence and accuracy failures** (F-3). Quote the reasons.
7. **Our side is least accurate at RC6** (0.0202 tolerance; σ_min 6.06e-4). Both tools are closer to the twin there. It is inside
   rule 3 by a factor of 5.
8. **Only `P_r`, only the registered states, SYN-001 only, IDAES at ε = 1e-8 K, procedural blindness.** §14, §17.11 and §18.9 apply
   verbatim.
9. **One platform.** The committed comparison is reproduced bit for bit on x86-64. A10 against a live solve on CI's second
   architecture is open (status lines above).

## 9. For Frank

- **Nothing here needs a decision from you to keep S03 moving.** S03 may close `tested` with X31's reference clause recorded as not
  met (§17.5, §13), after the `reviewer` pass, the gate and CI.
- **For information.**
  - X31's clause fails on one case only: RC4, the refluxed absorber. Neither DWSIM nor IDAES expresses or converges it under the
    registered rules.
  - Your Q-A2-4 decision, a third reference tool (S09), is the route. S09's specification must register how a third reference
    counts toward X31, because S03's rule is written for two tools.
- **Human numerical and process-modeling sign-off of S03 remains yours.** These verdicts do not stand in for it.
