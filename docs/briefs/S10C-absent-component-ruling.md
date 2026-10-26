# S10-C brief: the absent component's roundoff lift breaks C-MW on aarch64 (design lane, `architect`)

Branch `wp/S10C`, worktree `.claude/worktrees/s10c`, head `f1a0a058`. Everything else in S10-C is done: review passed
(F1 fixed), manifest `evidence/S10c/8f38f963…` tested, full local gate PASS at `cc0de30b` (13229 passed). CI run
40275276182: x86-64 and default-install pass; **aarch64 fails 3 tests, all C-MW**. Design `docs/derivations/S10C-design.md`
§7 Q4 says a Stage-A failure on a pinched case is escalated to the design lane, not tuned.

## 1. The question

Choose and specify the remedy, with an inertness/identity argument and the work order, so the build lane has nothing to
choose. Remedies are listed in §4; you may find another.

## 2. Diagnosis (build lane, `docs/S10C_DECISIONS.md` final "findings" section; `scripts/s10c_cmw_diagnose.py`;
CI dispatch run 40285056440 on scratch branch `wp/S10C-diag`; artifacts in
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/ci-diag/`)

- C-MW is a methanol–water column on the three-component `wilson-ig-v1` record set: ethanol (C2H5OH) is absent from
  every inlet, so 60 free columns sit at exactly +0.0 and their exact Newton step is zero.
- The bubble-point sweeps, start profile and Newton start `x⁰` are bitwise identical on local x86-64, CI x86-64 and CI
  aarch64 (282 columns). Divergence starts in Stage A's first Newton linear solve (BLAS kernels).
- **K03's Newton releases those zeros (R-064) only when `α_max = 0`.** When the 60 roundoff step entries all happen to be
  ≥ 0, the step is taken and lifts them to ~1e-15 mol/s; thereafter they are not exactly on the bound, R-064 cannot release
  them, and those roundoff flows cap every later step.
  | | lift at iteration | step caps | result |
  | --- | --- | --- | --- |
  | local x86-64 | 5 | 0.828 once | CONVERGED in 9 |
  | CI x86-64 | 5 | 0.294, 0.972, 0.99994 | CONVERGED in 10 (different final hash) |
  | CI aarch64 | 2 | 0.186 at it. 3, then 0 at it. 4 | BOUND_BLOCKED on `COL.stage.1.r.C2H5OH`; edge 3 stalls at λ = 2045/2048; Stage B has 0 candidates → `homotopy_stalled(BOUND_BLOCKED)`, 739.7 tol off on B |
- **x86-64 passes by luck:** 320 local solves with 1–4 ulp perturbations (x⁰, profile, sweep T, sweep K, Newton step
  entries, exp/log results): 160 HOMOTOPY_STALLED, 55 rescued by edge 3, 105 converge directly. Every blocked variable is a
  C2H5OH flow. `OPENBLAS_CORETYPE=Prescott` or `Sandybridge` alone fails locally; thread count is bitwise irrelevant.
- **Causal check** (scratch only): forcing the absent component's step to exactly 0 makes all 320 converge in 9 iterations,
  worst A41 ratio 1.3e-7. C-EW passes because it converges in 4 iterations, before any lift.

## 3. R-064 (`docs/decision-register.md` l.1767; normative `docs/derivations/K03-solver-spec.md` §5.3), pasted

**Decision.** When `α_max = 0`, the free components exactly on a finite lower bound at both the attempt's opening and the
current iterate that form a released set — the rows with `F == 0.0` exactly and every nonzero entry in the set number
exactly as many as the set's columns, so that, `J` being nonsingular, the exact step on the set is zero — get `d := 0`
exactly, and `α_max` is recomputed; `BOUND_BLOCKED` is declared only if a component outside the largest released set still
blocks. No record: the step taken is the exact Newton step.
**Rejected.** A start-dependence limitation; discarding the step on every exactly-zero flow (would freeze a component that
must leave its bound and hide T02 §6.3.3's disappearance, a `BOUND_BLOCKED` on a component that reached zero during the
attempt); pinning absent components as a form (changes every attempt's rows and records where a component is absent,
SC-1…SC-4 and NP-* included); a roundoff threshold on the outward direction (a tolerance on the exact path).
**Watch for.** The release widened to components that reached their bound during the attempt; the exactness conditions
relaxed to tolerances; **the release extended to every step, not only where `α_max = 0`, without its own inertness proof.**

## 4. Candidate remedies (build lane's list; none implemented)

- (a) Apply R-064's release (`d := 0` on the released set) on every step, not only at `α_max = 0`, with the same
  exactness conditions (opening and iterate exactly on the bound; rows `F == 0.0` exactly; square set). Needs the
  inertness proof R-064's "Watch for" demands and a whole-suite identity gate: which registered records move?
- (b) A structural zero for a component absent from every inlet (column- or case-scoped form; R-064 rejected the general
  form; needs an ADR).
- (c) Register C-MW/C-EW on a two-component record set (new registered cases; does not fix the general exposure).
- (d) Keep the typed outcome as a limitation (A40–A42 then platform-dependent, which R-627's classes do not cover).

## 5. Constraints

- `numerics/` and the K03 Newton core are shared by every solve: any change must be proved inert on every registered case
  except those the ruling names, with a gate (as S08/S10-C's G1 digests, and whole-suite records where needed).
- Frank's standing directive: as few limitations as possible; robustness first (cited by R-064).
- A fix must not depend on BLAS kernel or architecture; the evidence must include an aarch64 run (CI dispatch on a scratch
  branch is available: `wp/S10C-diag`, input `s10c_diag`).
- Never a tolerance on the exact path.

## 6. Deliverable

A short design note `docs/derivations/S10C-absent-component.md` (decision, rejected alternatives, inertness argument,
the gate and the work order with acceptance tests), register entries after R-781, an amendment to K03 §5.3 / R-064 if (a)
is chosen, an ADR only if a frozen interface or an accepted ADR changes. A docs-only commit on wp/S10C (include this
brief). You may run scratch measurements (the perturbation harness is at
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/harness/`). Do not push.
Report in at most 20 lines.
