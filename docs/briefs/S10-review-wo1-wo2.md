# S10 brief: `reviewer` pass on WO-S10-1 and WO-S10-2

Branch `wp/S10`, worktree `.claude/worktrees/s10`, head `83841192`. The range is `main...wp/S10`. The code under
review is about 1100 lines in `src/openflowsheet/thermo/wilson_ig.py` and `thermo/stability.py`, plus tests
`tests/test_s10_provider.py` and `tests/test_s10_flash.py`.

## 1. The design it was built against

- `docs/derivations/S10-spec.md` §3–§5: closed forms, derivatives, the flash, the §4 convexity theorem with its
  stability search, and the message grammar.
- ADR 0047 (Proposed) and R-700…R-710.
- CLAUDE.md requires a design-lane review because this touches residuals, derivatives and phase logic.

## 2. What was run (build-lane reports)

- **`test_s10_provider.py`: 87 pass.** The worst agreement is 0.069 tolerance (E4 LIQUID ∂h/∂n_VB, 6.9e-14 relative),
  which equals FLOOR-E. Mutations move results by:

  | Mutation | Movement (× tolerance) |
  | --- | --- |
  | Transposed Λ | 1.9e12 |
  | Unprojected n-derivatives | 2.8e14 |
  | R = 8.314 | 1.9e8 (the spec says 1.9e8) |

- **`test_s10_flash.py`: 86 pass.**
  - Two-phase outputs: worst 0.034 tolerance.
  - Trial distances: worst 1.78e-14, equal to FLOOR-TM.
  - Component balance: 5.6e-17 n_tot.
  - Iterations: at most 40 / 39, equal to SS-CAP.
  - Mutation MF01 moves β by 1.27e9× tolerance; the spec says 1.3e9.
  - Labels match the YAML on every registered state.
- **Provider-registry tests:** 539 passed, 11 skipped, 6 failed. The 6 are T08 C3 "S10 has no U02 item in the
  harvest", which is expected until a manifest is harvested, as with S05 and S07.
- ruff, ruff format and mypy are clean.

## 3. Build decisions to rule on (`docs/S10_DECISIONS.md`)

B-1…B-15. These need a look in particular:

| Decision | What it does |
| --- | --- |
| B-4 | The general projection for the n-derivatives of ln φ |
| B-9 | Rachford–Rice safeguarded Newton from β = 0.5; the bracket halves at least every 3 iterations |
| B-10 | The liquid trial carries ln W |
| B-11 | A `not_converged` flash returns no outlets, per the spec, although `FlashResult`'s docstring says "carries what it reached" |
| B-14 | `achieved_accuracy` is left at "exact-double", as in other providers. The build lane flagged it for you |
| B-15 | ln γ factored out of `_wilson`, proved bit-identical at E1–E6 by hex dump |

## 4. Where to look hardest

- Whether the implemented stability search really is the §4 theorem's search: the closed-form vapour test plus one
  convex liquid search. Does it remain valid at the edges: absent components, a pure fluid, the 1e-10 band and
  dormant states? Is the label honest about its scope?
- Whether the residual and derivative paths describe the same function at the same state.
- Whether the tests verify what they claim, and whether any assertion is circular, for example comparing the code
  with values the code produced.

## 5. Not worth your time

Formatting, and re-deriving the generator's reference values (the specifier owns them).

## 6. Deliverable

- `docs/reviews/S10-review-wo1-wo2.md`, with findings ranked by severity and a ruling on each B-decision you question.
- Spec errata, if any, as a short dated amendment section, with a register entry after R-710.
- A docs-only commit on wp/S10. Do not push and do not set `reviewed`. Report in at most 25 lines.
