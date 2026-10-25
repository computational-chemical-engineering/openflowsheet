# S10 brief: Amendment 2, rulings after WO-S10-3 (design lane, `specifier`)

Branch `wp/S10`, worktree `.claude/worktrees/s10`, head `696a54bf`. The authority being amended is
`docs/derivations/S10-spec.md`, which already carries Amendment 1 (§14, E-1/E-2, R-711).

## 1. The question

Rule on the build lane's three escalations and one build decision from WO-S10-3. The ruling must leave WO-S10-3's
remainder with nothing to choose:
- `s10_records.py --emit` producing records.yaml and fit-report.json;
- the generator's real section;
- A34's flash half.

## 2. Facts

They are in `docs/S10_DECISIONS.md`. Read lines 41–57 (B-24, B-26, ESC-1, ESC-3, ESC-2, the Q-N1 note) and the
WO-S10-3 run-log line (about l.99). In short:

- **The fit data are final.** Kurihara, Nakamichi and Kojima (1993), Table II.
  - The three binaries have 11, 20 and 18 rows.
  - They were double-entered (A = B) and checked by the orchestrator against the 300 dpi page image, all 49 rows.
  - The file is `benchmarks/s10/vle/kurihara1993_binaries.csv`.
  - The paper also has the ternary (Table V), which is VAL-1.
- **ESC-1:** the methanol+ethanol fit fails §9.4 as written.
  - Gauss–Newton from θ = 0 crawls along the singular line θ12 = −θ21 and hits the 200-iteration cap at Φ = 4.564e-4,
    which is not a minimum.
  - The true minimum is θ* = (0.492781, −0.404717), Φ* = 4.35349e-4.
  - The 0.05-step grid is too coarse to certify it; a 0.005-step grid finds the valley.
  - The system is nearly ideal: γ is 0.958–1.018, and the paper's own NRTL parameters for it are zero.
  - The build lane's options: (a) multi-start Gauss–Newton from the local minima of a 0.005-step grid, with the
    global claim on that grid; (b) Λ = 1 for this pair; (c) as written, which gives no records. Its default is (a).
  - The water binaries are well posed under both grids.
- **ESC-2:** the paper prints 101.3 kPa, and B-24 uses it. Using 101.325 kPa moves Λ by at most 2.8e-3 relative and
  AAD(T) by at most 0.001 K.
- **ESC-3:** registered states I9, I10 and I13 fail §8.1's IDAES-envelope margin on the provisional records.
  - I9 is 0.28 K from IDAES's approximate dew.
  - I10 is 0.03 in z from the model azeotrope, so its band is 0.007 K.
  - I13 is 0.43 K from the approximate dew.
  - These depend on Λ only weakly.
  - The options offered: move I9 and I13's T into [T_bub, approx dew]; replace I10 (for example z_E = 0.4); or drop
    the margin for those states.
- **B-26:** minimum-norm Gauss–Newton steps, because at θ = 0 the two Jacobian columns are identical for every binary.
- **Rights:** S10-RC-03 (CoolProp output) was marked "permitted with the MIT notice", on the spec's own reading that
  tool output copies no EOS constant. Confirm or correct that reading.
  - S10-RC-05 (the paper's numbers) is unresolved. The paper carries only "© 1993 American Chemical Society".
  - Frank decides on shipping after the rights check (Q-F3).

## 3. Constraints

- Never loosen a fit claim to pass. Any new procedure must be pre-registered and must give the same results for the
  water binaries.
- Fit quality is not validation.

## 4. Deliverable

- Amendment 2 as a new §15 of the spec, with pointers from §8.1 and §9.4: the exact procedure text, the moved or
  replaced states, and the confirmed pressure.
- Generator changes, with `--check` passing.
- Register entries after R-711.
- A docs-only commit on wp/S10. Do not push. Report in at most 20 lines.
