# S03 brief: Amendment 2, after IDAES qualification (design lane, `specifier`)

Branch `wp/S03`, worktree `.claude/worktrees/s03`. Its head at writing time contains WO-S03-1, WO-S03-3, WO-S03-3b,
WO-S03-1b and the IDAES branch merge. The authority is `docs/derivations/S03-spec.md` as amended by §17
(Amendment 1, R-634…R-639).

## 1. The question

IDAES qualified 8 of its 18 applicable cases, and its positive control PC-P is among the 10 that failed. Under §17.3(b)
that makes every IDAES pair `NOT_COMPARABLE(control_not_comparable)`, so no case would have two references.

Decide:
- whether the IDAES records stand as they are;
- or whether a registered change, made blind and before any comparison, is justified. Candidates are the
  initialization policy, the SmoothVLE ε, the Ipopt options, or a different IDAES positive control.

Then state what X31 and D19 can claim either way.

## 2. Measured facts: IDAES (WO-S03-2, branch `wp/S03-idaes`)

The records are at `6d9486a0` and the decisions B2-1…B2-8 are in `docs/S03_BUILD_DECISIONS.md`, section "WO-S03-2".

- **Available at L3:** RC1, RC1-RR, RC1-BR, RC1-z and RC7. The partial condenser is a `Flash` with its outlet pressure
  fixed.
- **Available at L2:** RC2, RC2-B and RC2-z. These use `TrayColumn` with B as an L2(b) equation.
- **Accuracy rerun on the 8:** RC1 moves at most 0.0069 tolerance; the others ≤ 1.8e-5.
- **Rules 2–2d on the 8:**

  | Check | Worst value |
  | --- | --- |
  | Component balance | ≤ 1.7e-10 mol/s |
  | Energy balance | ≤ 1.7e-5 W |
  | SmoothVLE shift | 5.0e-9 K |
  | Pressure deviation | 0 Pa |
  | Specification residual | ≤ 2.1e-15 |

- **Not available. Ipopt does not converge at ε = 1e-8 K:**
  - RC3, RC3-Q, RC3-z and RC5 stop at "Solved To Acceptable Level" after 6–14 iterations.
  - RC4, RC4-D, RC4-z and PC-P run to 500 iterations.
  - RC2-RR stops at acceptable at L2 and runs to 500 iterations at L3.
- **RC6** converged at L2, but its accuracy rerun moved 0.34 tolerance, which fails 2d. At L3 it ends locally
  infeasible.
- **PC-L** is not applicable, as registered.
- **The engineer's diagnosis, not ruled on:** the stalled solves end on the SmoothVLE rows of the trays' inlet blocks.
  - IDAES's `Tray` re-flashes every inlet. Saturated streams sit at the kink, where ε = 1e-8 K makes the problem
    ill-conditioned; dual infeasibility reaches 1.8e14.
  - The outcome depends on the starting point: RC2 converged from one pilot start and stopped at "acceptable" from
    another.
- **B2-4, the engineer's isolated choice, judged by convergence on RC2/RC3 pilot runs:**
  - The initializers run at IDAES's default ε, and the registered ε = 1e-8 K is set before the final solve and the
    rerun.
  - At 1e-8 K, IDAES's own `TrayColumn.initialize` fails on RC2.
  - This departs from T06's application note, which sets ε before the initializers.
- **Q-S03-7 is answered no.** IDAES's partial `Condenser` has no liquid-distillate variable, so every partial-condenser
  case went to L3.

## 3. Measured facts: DWSIM (WO-S03-3 and WO-S03-3b, on wp/S03)

- **Available, 10 of 19:** RC1, RC1-RR, RC1-z, PC-L, RC2, RC2-RR, RC2-B, RC2-z, RC5 and RC6. RC6 is at (L1, 1e-10,
  Napthali–Sandholm) and its rerun moved 6.6e-9 tolerance.
- **Not available:**
  - RC1-BR (rerun 0.1006, above 0.1) and PC-P;
  - RC3 family: N–S hits 1000 iterations; W–H fails DWSIM's mass-balance check, and rule 2's balance at 1e-7 and 1e-6;
  - RC4 family: no vapour-distillate rate exists at L1, and L2(a) errors under both methods;
  - RC7: DWSIM's temperature spec reads only stage 1 or stage N.
- DWSIM's control is PC-L, which is available, so DWSIM's pairs count under §17.3.

## 4. Per-case availability across the two tools

| Case | DWSIM | IDAES |
| --- | --- | --- |
| RC1, RC1-RR, RC1-z | yes | yes |
| RC1-BR | no (2d 0.1006) | yes |
| RC2, RC2-B, RC2-z | yes | yes |
| RC2-RR | yes | no (Ipopt) |
| RC3 family | no | no |
| RC4 family | no | no |
| RC5 (purity) | yes | no (acceptable stop) |
| RC6 (recovery) | yes | no (2d 0.34) |
| RC7 (temperature) | no (capability) | yes |
| PC-P | no | no |
| PC-L | yes | n/a |

If IDAES's control is restored, the cases with both references are RC1, RC1-RR, RC1-z, RC2, RC2-B and RC2-z.

## 5. What to decide

1. **Rule 4 allows levels and rungs to change only during blind qualification.** Is a registered change to IDAES's
   initialization, ε schedule or Ipopt options admissible now? No comparison has been run, and nobody has seen a twin
   or ours value. If it is admissible, register exactly what changes and the order of attempts, and apply it to every
   IDAES case rather than only the failures. If it is not, say so.
2. **B2-4:** endorse it, or replace it.
3. **The IDAES positive control.** If PC-P stays unavailable, is there a control IDAES can express that discriminates
   as PC-P was meant to? Derive it the way §3.3 derived PC-P and PC-L, or rule that IDAES has none and say what
   follows.
4. **Outcomes:** X31's per-case table (§17.5) and D19's claim under the facts, for both branches of item 1.
5. **Whether the IDAES harness needs a re-run work order, and what it is.** After that comes WO-S03-4 (classifier,
   gate test, manifest) and WO-S03-5 (verdict).

## 6. Constraints

- Never loosen a tolerance or threshold. No substitution of a different model.
- Blindness holds: nobody has compared any tool record with ours or the twin, and the ruling must not depend on one.
- Every attempt is recorded. A failed run is a result.

## 7. Deliverable

- Amendment 2 as §18 of `docs/derivations/S03-spec.md`, with pointers from the sections it changes.
- Register entries after R-639.
- Work-order deltas.
- A docs-only commit on wp/S03, not pushed. Report in at most 30 lines.
