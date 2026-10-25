# S03 brief: two independent column references (design lane, `specifier`)

Branch `wp/S03`, worktree `.claude/worktrees/s03`, from main `0f1a9d37`. Frank chose the workstation backlog on
2026-10-24, and S03 comes first.

## 1. The question

Write the S03 specification. It must say:
- which two independent references the column model is compared against;
- on which cases, with matched semantics;
- with which tolerances and verdict mechanics;
- the perturbation studies;
- the "supported nonideal scope" statement;
- the decisions S02 deferred to S03.

The spec must be concrete enough that build-lane work orders can be executed without choosing anything scientific.

## 2. Why it is design-lane work

- It is a benchmark registration and reference-comparison design: matched-model semantics, independence disclosure,
  tolerances and verdicts.
- It owns requirement D19's column part and gate X31's "two independent references where available".
- No test exists that would catch a wrong choice here.

## 3. Authority text

- Plan `docs/implementation-plan.md`:
  - l.283 S03: "Two independent column references across the available suite, perturbation studies and supported
    nonideal scope; rate-based models remain deferred". It depends on S02, and R01 depends on S03.
  - l.314 D19: "Matched-model inputs, independence disclosure and verdicts" (packages T06, S03, R01).
  - l.357 X31: "Four matched column cases, invalid specs/phases, two independent references where available" (S02/S03).
  - l.345 V16: "two both-reference cases where feasible" (owner T06).
- `docs/requirements.yaml`:
  - l.420–427: D19 is `planned`, with no tests and no evidence.
  - l.858–862: X31's verdict is null.
  - l.1106–1110: the S03 row is `planned`.

## 4. What the column model is today (facts from recon)

- Code: `src/openflowsheet/models/syn001/column.py` and `column_solve.py`.
  - `ColumnSpec` is at l.376 and the refusals S1–S10 at l.756.
  - `INVERSE_KINDS` (purity, recovery, temperature) is at l.142, and `END_KINDS` at l.150–151.
- End specifications:
  - condenser: reflux_ratio, distillate_rate, duty, purity, recovery, temperature;
  - reboiler: boilup_ratio, bottoms_rate, duty, purity, recovery, temperature.
- Condenser kinds are none, partial and total. Reboiler kinds are none and partial; a total reboiler is unsupported.
- Thermo: SYN-001 only, an ideal three-component fixture with composition-independent K (S02-spec §14, l.329–345).
  PR routes are vapour-only. A real-chemistry column needs a liquid-capable mixture method, which does not exist.
  S05 (`iapws95-v1`) and S07 (`coolprop-heos-v1`) are pure-fluid and library-only (Frank: "library only for now").
- Not established (S02 §14): independent column references, sensitivity results, uniqueness, hydraulics, efficiencies,
  side draws and rate-based models.
- Registered cases:
  - S02 §9 (l.236–261): M1 partial/partial, M2 total/partial, M3 stripper, M4 refluxed absorber, P1 phase case, and
    the variants V-M1, V-M2, X-DB, S-R5. Their expected values come from the project's own generator
    (`docs/derivations/scripts/s02_reference.py`, 906 claims), which is not independent. S02-spec l.260–261 says
    "S03 owns the two independent references".
  - S06 §9 (l.238) adds inverse-spec cases (`docs/derivations/scripts/s06_reference.py`).
- Deferred to S03:
  - S02-spec l.356, open question 5 / R-554 (`docs/decision-register.md` l.11135): the block rule.
  - R-533 (`docs/S02_DECISIONS.md` l.117): the P1 outcome.
  - R-534 (l.10839): S02 cases and the independent reference.
  - R-508 (l.10508): S01 tolerances and independent reference, as precedent.

## 5. The precedent to follow: T06's reference comparisons (D19 for other units)

- `docs/derivations/T06-corpus-spec.md` §9 (l.619–680):
  - eight fixtures, REF-01…REF-08, plus the positive control PC-2;
  - §9.3 matched semantics, §9.4 tolerances, §9.5 verdict mechanics, §9.6 what is not compared.
  - REF-08 is a SYN-001-nominal recycle with a flash, so SYN-001 thermo has already been matched in both tools.
- `docs/reference-environments.md` covers the two tools:
  - IDAES: idaes-pse 2.13.0 with extensions 3.4.2;
  - DWSIM: 9.0.5 driven through pythonnet 3.1.0.
  - It also records the licences, the fingerprint and the matched-semantics decisions (§7). It contains no
    comparison with this project.
- Blind qualification: `docs/t06-reference-qualification.md`. The tool harnesses are in `spikes/references/`.
- Evidence layout: `benchmarks/t06/references/`, which holds the results per (fixture, tool), `comparison.json` and
  SHA256SUMS. The verdict is `docs/reviews/T06-verdicts.md`, written by the `verdict` agent: "All 16 (fixture, tool)
  pairs are AGREE".
- The policy is ADR 0014. The disclosure wording reads: "Numerical verification of a second, independent
  implementation of the same equations, not empirical validation".
- The environments are being rebuilt now by `scripts/build-reference-envs.sh all` in the S03 worktree. They are
  git-ignored: `.venv-idaes/`, `.venv-dwsim/`, `.reference-downloads/`.

## 6. What is open (decide each)

1. **The references.**
   - IDAES (its tray-column / MESH models) and DWSIM (its rigorous distillation column) with SYN-001's matched thermo
     are the obvious pair. Whether each tool can express SYN-001's composition-independent K and its enthalpy model
     inside a column is not yet known.
   - Specify a blind qualification work order that settles it, and a pre-registered rule for "where available" if a
     tool cannot express the matched model. Never substitute a different model silently.
2. **Cases.** Which of M1–M4, P1 and the S06 inverse-spec cases are compared, against which tool, and which
   quantities. X31 says four matched column cases.
3. **Matched semantics** per tool: specifications, stage numbering, feed stage, condenser and reboiler conventions,
   pressure profile, enthalpy datum and initialisation. Follow T06 §9.3's form.
4. **Tolerances and verdict mechanics**, derived the way T06 §9.4–§9.5 derive them.
5. **Perturbation studies.** What "perturbation studies" means here (for example spec sweeps or feed perturbations,
   compared across tools or against the project's own sensitivities). Sensitivities of columns are "not
   established" in S02.
6. **"Supported nonideal scope".** With no liquid-capable mixture method, what S03 states. The likely answer is an
   explicit "none supported" with the refusal evidence, but decide it and give the reason.
7. **The deferred items:** the block rule (R-554), the P1 outcome (R-533), and R-534.
8. **Evidence and verdict:** the manifest check list, and who writes the verdict (the `verdict` agent, as T06).

## 7. Constraints

- Do not re-plan or reopen the column model. Rate-based models stay deferred.
- No new external tool beyond the two T06 environments without saying why. The licences for those two are recorded.
- Reference results are numerical verification, not empirical validation. Self-generated values are regression
  fixtures.
- Gating follows CLAUDE.md: docs need no gate, code runs the tests it touches, and the full gate runs before merge.

## 8. Deliverable

- `docs/derivations/S03-spec.md`, containing:
  - numbered falsifiable assertions;
  - registered cases;
  - matched semantics;
  - tolerances;
  - verdict mechanics;
  - a manifest check list;
  - work orders sized at about 150k context each (qualification, harness, runs, comparison, verdict);
  - open questions with recommended defaults.
- Register entries in `docs/decision-register.md`, starting at the next free R-number.
- A docs-only commit on `wp/S03`. Do not push. Report in at most 30 lines.

## 9. Out of scope

New thermo for columns, binding S05/S07 into flowsheets, hydraulics, efficiencies, side draws, and the R01 corpus.
