# S10-C brief: R-782 after its CI evidence — one G-R7 stop and the review's two should-fixes (design lane, `architect`)

Branch `wp/S10C`, worktree `.claude/worktrees/s10c`, head `03ef9e2e` (review committed). Design
`docs/derivations/S10C-absent-component.md` (§4.6 table, §4.7 rulings, §6 gates incl. G-R7, §7), R-782, R-783; review
`docs/reviews/S10C-r782-review.md`; build log `docs/S10C_DECISIONS.md` ("R-782 (absent-component release)").

## 1. What CI showed (dispatch run 40295256025 on scratch `wp/S10C-diag2` = `1bc65b86` + the gated diag job)

Artifacts downloaded to `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/ens-ci/`
(`ensemble-ubuntu-latest/`, `ensemble-ubuntu-24.04-arm/`: `run2r-*.json`, `run2r-*.a98.txt`, `holdout1-*.json`,
`*.report.txt`, `*.replay.txt`; `s10c-diag-*/cmw.json`, `cew.json`).
- **G-R3 half:** `s10c-diag` on aarch64: C-MW `CONVERGED` in Stage A, one attempt, 9 Newton iterations (was
  `homotopy_stalled(BOUND_BLOCKED)`); C-EW `ColumnSolution`. x86-64 likewise. (Normal CI on `wp/S10C` is still running.)
- **G-R7 CI half:** both `ensemble` jobs exit 1 at the `t06_ensemble.py a98` step against the committed run 2 record
  (as §4.7 expected — "a later A98 comparison against run 2 will report these starts as class changes"):
  - ci-x86-64: `DISCREPANCY THM-08 03 / THM-08 12 / THM-09 04: class SUCCESS, run 2 F-BUDGET` (failure → SUCCESS, as
    §4.6). 187 final states differ bitwise (reported).
  - ci-aarch64: the same three failure → SUCCESS, **plus `DISCREPANCY THM-09 03: class F-FALSE-SUCCESS-CAUGHT, run 2
    F-BUDGET`** — a failure-class change that is not failure → SUCCESS. 17 final states differ bitwise. G-R7's criterion:
    "every class change is failure → SUCCESS. Any other change stops for the design lane." Hence this brief.
  - Because the job stops at `a98`, the holdout comparison against committed `holdout1` was not run in CI; the
    `holdout1-ci-*.json` outputs exist in the artifacts. `ensemble-compare` (x86-64 vs aarch64) succeeded.

## 2. The review's two should-fixes (`docs/reviews/S10C-r782-review.md` F1, F2)

- **F1:** `_released` (`numerics/newton.py:873-891`, unchanged R-064 code) uses a recursive matching; R-782 now runs it on
  every iteration of a solve with an absent component. 0.4 ms at 60 columns, 1.5 s at 10 000, `RecursionError` for one
  absent component across 1 000 stages. No registered case exceeds 60 columns; R-064 already reached it at the first
  blocked step. Reviewer default: an iterative matching in a separate commit after the merge (the result is unique, so
  no answer can move).
- **F2:** A41 records but does not assert that C-MW/C-EW's absent flows end exactly +0.0; a partial regression would pass
  on x86-64. Reviewer default: assert it for C-MW and C-EW, which needs a register entry overriding R-780's "exact zeros
  not required" for those two cases.

## 3. Rule

1. **THM-09/03 on aarch64:** analyse the record (its run-2 F-BUDGET versus its R-782 F-FALSE-SUCCESS-CAUGHT: what the
   solver returned, why the verifier caught it, whether R-782's release is what changed its path, and whether it is a
   regression in substance — a start that used to exhaust its budget now converges to a state the verifier rejects).
   Decide: accept (and amend G-R7's criterion and §4.6, with the reasoning), or a change to the rule, or other. Also
   complete G-R7's holdout half from the artifacts against committed `holdout1` on both classes.
2. **F1** and **F2**: accept or change the reviewer's defaults, with exact text (and the register entry for F2).
3. Whether any of this changes the work order before WO-R4 (manifest) and the merge.

## 4. Constraints

Never restore the lift; never a tolerance on the exact path; never edit a committed run record. Frank's directive: as few
limitations as possible.

## 5. Deliverable

A dated amendment section in `docs/derivations/S10C-absent-component.md`, register entries after R-783, a docs-only commit
on wp/S10C (include this brief). Scratch analysis scripts outside the repo or under `docs/derivations/scripts/` if they are
the evidence. Do not push. Report in at most 20 lines.
