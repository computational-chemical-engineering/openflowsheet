# S03 brief: Amendment 1 (design lane, `specifier`)

Branch `wp/S03`, worktree `.claude/worktrees/s03`, head `2d48a30b`. The authority being amended is
`docs/derivations/S03-spec.md`, committed at `901b33e9` with register entries R-628…R-633.

## 1. The question

Amend S03 for four things in one round:
- Frank's two answers;
- the DWSIM qualification's contradictions with §5.2;
- the A03 exemption the build lane needs;
- the effect of PC-P being unavailable in DWSIM.

The result must leave WO-S03-2 (IDAES), the DWSIM re-run for any new cases, and WO-S03-4 with nothing to choose.

## 2. Frank's answers (2026-10-24, recorded in `docs/FRANK_QUESTIONS.md`)

- **Q-S03-5: "All three".** S03 checks all three of S06's inverse specifications against the tools: purity (RC5,
  already registered), recovery and temperature. Register the recovery and temperature cases the way RC5 was
  registered (S06's cases at `P_r`, with a ratio partner). Extend `s03_cases.json` and `s03_reference.json` through
  the generator, and keep `--check` byte-identical apart from the additions.
- **Q-S03-4: "Yes, plan a package".** All-liquid or all-vapour column sections should converge, in a later package
  rather than in S03. S03 keeps the typed failure as a registered limitation. Record the queued package in the spec's
  "does not establish" section and in the register.

## 3. What has been done (facts)

- **WO-S03-1, merged into wp/S03 at `1f49b6f9`.**
  - S11 is `property_method_refusal` in `models/syn001/cascade.py`. It is the first statement of `cascade.validate`
    and of `column.validate`.
  - The A04/A05 tests pass, 15 of them. The cascade/column test files with S11 in place give 574 passed and 0 failed.
  - Our side passes all 16 cases within 0.1 tolerance of the twin. The worst is RC3 at 3.5e-3 tolerance, on
    `bottom[B]`.
  - The records are in `benchmarks/s03/references/results/ours-*.json`.
- **WO-S03-3, DWSIM, run blind at `95870140`.** The decisions and questions are in `docs/S03_BUILD_DECISIONS.md`,
  section WO-S03-3, l.6–94; read l.65–94 for the outcome. Summary:
  - **Available at L1, (1e-8, Wang-Henke):** RC1, RC1-RR, RC1-z and PC-L. The accuracy rerun moves them by 0.071,
    0.079, 0.093 and 0.071 tolerance.
  - **Available at L1, (1e-10, Napthali-Sandholm):** RC2, RC2-RR, RC2-B, RC2-z and RC5. The rerun moves them by 0.000
    and 0.017.
  - **No uniform rung exists,** so each case took its own first passing rung.
  - **RC1-BR is not available.** Only Wang-Henke at 1e-8 passes rules 2–2c, and its rerun moves 0.1006, which fails
    2d.
  - **PC-P is not available.** Wang-Henke fails DWSIM's own mass-balance check from 1e-10 to 1e-8, and fails the rule-2
    balance (3.1e-8 mol/s) at 1e-7 and 1e-6.
    - So under §7.2, DWSIM's RC1 and its three perturbations become `NOT_COMPARABLE(control_not_comparable: PC-P)`.
      DWSIM then has no comparable RC1-family case.
  - **RC3, RC3-Q and RC3-z are not available.** Napthali-Sandholm reaches 1000 iterations at every tolerance, and
    DWSIM reports "Unable to find column solver" for Burningham-Otto.
  - **RC4, RC4-D and RC4-z are not available.**
    - At L1 there is no native option for D = V_1. DWSIM's condenser rate option is the liquid distillate, which a
      full-reflux condenser holds at 0.
    - At L2(a), a partial condenser with liquid distillate 0 fails with "Error evaluating error functions".
- **Contradictions with §5.2's ladder:**
  - Russell inside-out does not exist in DWSIM 9.0.5.
  - Burningham-Otto runs only in DWSIM's absorber with no condenser and no reboiler.
  - Napthali-Sandholm defines the condenser reflux ratio as L/(liquid distillate), so it fails every partial-condenser
    case with an RR or D spec. Wang-Henke uses L_1/V_1.
  - DWSIM's column errors whenever its own relative component balance exceeds 10× the column tolerance, so Wang-Henke
    gets through only at 1e-8.
  - The build lane's questions:
    - Q3-1: amend §5.2? Its default is no. Wang-Henke is outside RC3/RC4's ladder and was not run into the records.
    - Q3-2: do the 8 cases stay NOT_COMPARABLE? Its default is yes.
- **A03 blindness:** T06's `t06_fixtures.py` and `t06_qualify_dwsim.py` contain the strings "twin" and "comparison".
  The S03 DWSIM script imports them for SYN-001's matched thermo. A03 as written would fail on them. The build lane
  proposes exempting these T06 modules (B3-2).
- **Environment:** DWSIM 9.0.5 runs on the pinned .NET 8.0.31, and the fingerprint matches
  `docs/reference-environments.md` §3. .NET 8 support ends on 2026-11-10. IDAES (WO-S03-2) has not run yet.

## 4. What to decide

1. The new recovery and temperature cases: their definitions, quantities, perturbations if any, and the twin values
   from the generator.
2. §5.2's ladder for DWSIM given the facts above. Never pick a rung after seeing a comparison. The DWSIM runs were
   blind, and any amendment must keep that property. State whether the existing DWSIM records stand.
3. PC-P in DWSIM. Is losing DWSIM's whole RC1 family to the control's unavailability the intended reading of §7.2? If
   §7.2 is amended, derive the replacement, for example a different positive control DWSIM can express. Do not
   loosen a tolerance.
4. A03's exemption list.
5. Whether "two independent references where available" (X31) is still met for each case when DWSIM lacks RC3/RC4,
   given that IDAES is still to run. Pre-register what the verdict says if IDAES also fails a case.
6. The Q-S03-4 package entry, the limitation text and its register entry.

## 5. Deliverable

- Amendment 1 as a new section of `docs/derivations/S03-spec.md`, with pointers from the sections it changes.
- Generator outputs extended, with `--check` passing.
- Register entries at the next free R-number after R-633.
- Work-order deltas for WO-S03-2, a DWSIM top-up run for the new cases, and WO-S03-4.
- A docs-only commit on wp/S03, named paths only, not pushed. Report in at most 30 lines.

## 6. Out of scope

Running any tool, editing the harnesses or records, and the one-phase-section package itself.
