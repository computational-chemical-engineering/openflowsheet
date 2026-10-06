# Design brief — the clearsheet diagnostic workbench (web shell, M06)

For design exploration in Claude Design. Paste this whole document as the brief. Everything
quoted as data below is real output of the simulator at commit `78d3647`; the chemistry is the
synthetic test package SYN-001 (invented components A, B, C).

## 1. The product in one paragraph

clearsheet is an open, agent-native steady-state chemical process simulator. Engineers and AI
agents build the same flowsheets through the same operations (inspect, edit, execute, compare),
and every result comes with its evidence: which equations were solved, how the solver got there,
what failed on the way, and an independent verification certificate. The web workbench is the
human's window onto that evidence. It is **not** a drawing tool first: blueprint §12 says "the
early web workbench prioritizes model inspection, DOF diagnostics, raw/scaled residuals, attempts,
phase changes, and branch comparisons. A minimal canvas follows reliable headless workflows.
Equations and units are reachable from every diagnostic; education mode exposes the relevant
transformations. GUI operations use the same revision and application contracts as agents."

## 2. Who uses it, and for what

- **A process engineer** checking a flowsheet an agent built or changed: is it well-posed, did it
  converge, is the answer verified, what exactly changed between two revisions?
- **A numerical-methods person** diagnosing a hard case: which attempt failed, why, where the
  residual sits, what the recovery path did, whether the Jacobian is near-singular.
- **A student** (education mode): how the model became equations, what the degrees-of-freedom
  count means, why a specification set is over- or under-determined.
- **An agent's human supervisor**: what the agent did (history of transactions), what it was
  allowed to do, and whether anything it reported as verified actually is.

## 3. Principles the design must carry

1. **Evidence over reassurance.** A green light means a certificate says VERIFIED; CONVERGED
   without verification is visibly different; a typed failure is a first-class, readable result,
   not an error toast. Never show "success" where the system only reports "converged".
2. **Equations and units one step away** from every number, stream and diagnostic.
3. **Same operations as agents.** Every button maps to an application operation (below); no
   GUI-only state or shortcuts that bypass validation.
4. **Honest status vocabulary**, kept distinct everywhere: implemented / tested / reviewed /
   released; numerical verification vs empirical validation; observation vs inferred cause.
5. **Dense but calm.** Engineering users read tables; design for scanning large stream tables and
   long traces, with tabular numerals and SI units (mol/s, K, Pa, W).

## 4. The operations the UI exposes (blueprint §11.2)

| Group | Operations |
| --- | --- |
| Inspect | Summary, model registry, unit/stream/equation views, DOF report, trace slices, failure evidence |
| Edit | Begin, add/replace model, connect, set specification, preview, validate, commit, rollback |
| Execute | Compile, initialize, solve, cancel, resume compatible checkpoint, verify |
| Compare | Branch, semantic diff, compare runs, compare plans, replay |
| Study (later) | Sweep, sensitivity, estimate, optimize, experiment plan, surrogate validation |

Permissions are separate (read, draft edit, execute, model installation, policy administration,
publication); the UI shows what the current user or agent may do, and policy changes are
explicit transactions — a solve button can never weaken verification.

Long work is a **job** with progress, cancellation and artifacts. Job events stream outputs
before the job ends; a job may produce 0..n outputs (for example 440 robustness solves).

## 5. Screens to explore

1. **Revision overview.** Flowsheet (small, auto-laid-out, not a CAD canvas), revision id and
   status (DRAFT / READY_FOR_SIMULATION / INVALID), last run and its verdict, open issues.
2. **Validation and degrees of freedom.** The ordered check list (schema, dimensions, graph,
   components, structure) with PASS / FAIL / NOT_RUN; the structural counts; for a failure, the
   implicated units and candidate specifications, clickable to their equations.
3. **Solve run.** Outcome, attempt tree (attempts, their phase signatures, why each closed), the
   recovery path taken, counters (residual/Jacobian calls, factorizations, property calls), time.
   A trace view of the event stream, filterable by attempt and event kind.
4. **Certificate.** Verification status, checks by result, local regularity, scaled error bound,
   limitations (e.g. `near_threshold`), comparison to a registered root where one exists.
5. **Streams and units.** Stream table (component flows, T, P, vapour fraction, phase split),
   unit duties/work/extents, with each value linking to the equation rows that fix it and to raw
   and scaled residuals.
6. **Failure bundle.** Taxonomy, observations vs inferred causes, attempt tree, best checkpoint
   and what it is verified for, replay identity, ranked suggested actions.
7. **Compare.** Two revisions (semantic diff: added unit, changed specification) or two runs
   (different roots, different paths), side by side.
8. **Agent history.** Transactions an agent made: expected revision, idempotency key, diff,
   validation result, who authorized it.
9. **Education mode** (a toggle, not a separate app): the same screens annotated with the
   transformations (units → equations → structural matrix → solve).

## 6. Real data to design with

**A verified run — case NET-02** ("high recycle whose fixed point depends on r"). Units:
FEED → MIX → HEAT → PHF (PH flash) → SPLIT → product, with S4 to a vapour product and S6
recycled from SPLIT to MIX. Path `revision_eo`, policy `T06-revision-v2`. First attempt closed
`BOUND_BLOCKED` ("a component sits on its lower bound and the Newton direction points out of the
feasible set; no trial can be taken along it"); the recorded recovery path
`traversal-G0-pass8-v1` then `CONVERGED` in 5 Newton iterations. 9 residual calls, 6 Jacobians,
6 factorizations, 338 property calls, 173 ms. Certificate `cert-1cf23ff02335`: VERIFIED, 144 of
144 checks pass, regularity NO_RANK_LOSS_DETECTED, scaled error bound 4.74e-6, limitation
`near_threshold`; 43 coordinates compared with the registered root, worst 1.86e-2 of its
allowance at `S3.liq.C`. Duties: HEAT.Q 31487.6 W, PHF.Q 20000 W.

| Stream | A mol/s | B mol/s | C mol/s | T K | P kPa | Vapour fraction |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | 1 | 1 | 1 | 300 | 100 | — |
| S6 | 6.64427 | 11.5137 | 15.8258 | 358.541 | 100 | — |
| S2 | 7.64427 | 12.5137 | 16.8258 | 353.792 | 100 | — |
| S3 | 7.64427 | 12.5137 | 16.8258 | 358 | 100 | 0.01541 |
| S4 | 0.650302 | 0.394016 | 0.167065 | 358.541 | 100 | — |
| S5 | 6.99396 | 12.1197 | 16.6587 | 358.541 | 100 | — |
| S7 | 0.349698 | 0.605984 | 0.832935 | 358.541 | 100 | — |

**Its trace** (27 events): `plan_built` → `region_opened` (solve_eo over FEED, MIX, HEAT, PHF,
SPLIT) → attempt 0: jacobian, linear_solve, step_accepted, jacobian, linear_solve,
`attempt_closed BOUND_BLOCKED` → attempt 1: jacobian, linear_solve, trial, trial, step_accepted,
then three jacobian/linear_solve/step_accepted rounds → `attempt_closed CONVERGED` →
`region_closed CONVERGED` → `solve_closed CONVERGED`.

**A failure bundle** (the same case with its recovery switched off): outcome `BOUND_BLOCKED`,
taxonomy "rank/linear/globalization failures", 1 attempt, 1 iteration, unscaled residual
1116.72; attempt tree: attempt 0 with phase signature HEAT TWO_PHASE, PHF TWO_PHASE; a best
checkpoint `region-attempt-0` over 47 variables (S1.n.A … S5.N) with its state hash; no inferred
causes recorded (the design must handle empty sections gracefully).

**A validation failure — case STR-03** ("excess specification"): status INVALID; structure 47
free variables, 50 equations, 47 matched; check STR-03 FAIL: "STRUCTURAL_OVER_SPECIFICATION:
excess 1; over-specified units ['U-HEAT']; candidate specifications ['SPEC-feed-n-A',
'SPEC-feed-n-B', 'SPEC-feed-n-C', 'SPEC-feed-T', …]". Earlier checks (SCHEMA-01, DIM-01,
GRAPH-01/02, COMP-01/02/03) PASS.

**Corpus-level numbers** (for a project dashboard, if you propose one): 49 registered cases; 30
in the success set, all verified; robustness ensemble 434 of 440 perturbed starts succeed on the
gated run (gate ≥ 418) on both x86-64 and aarch64, with 0 false verifications; 16 of 16
comparisons with DWSIM and IDAES agree. A working read-only page with all 49 cases exists:
https://claude.ai/artifact/4yqYspZ3jPmowoxvTeSekm (private to the project owner).

## 7. Constraints

- Desktop first (wide tables, side-by-side compare), but readable on a tablet; light and dark.
- Accessible: keyboard navigable, colour never the only carrier of status (pill text + colour).
- Numbers: tabular figures, SI units shown in headers, no silent rounding of values used in a
  comparison; show full precision on demand.
- Status vocabulary (use exactly; from `schemas/`): verification VERIFIED / RELAXED /
  UNVERIFIED / FAILED; validation DRAFT / READY_FOR_SIMULATION / INVALID; replay MATCH /
  MISMATCH / NOT_RUN; solve outcomes CONVERGED or one of 20 typed failures, for example
  BOUND_BLOCKED, BUDGET_EXHAUSTED, ACTIVE_SET_CYCLING, STAGNATION, LINEAR_SOLVE_FAILED,
  SPECIFICATION_CONFLICT, HOMOTOPY_STALLED, PTC_STALLED — design for a long, open list.

## 8. Out of scope for this exploration

A drag-and-drop P&ID or CAD canvas (a minimal flowsheet view is enough), dynamics, optimisation
studies, real-plant connectivity, marketing pages, and the brand name (keep "clearsheet" as a
working name).

## 9. What to deliver

A small design system (type, colour tokens for light and dark, status pills, table and trace
styles) and screens 1–6 at desktop width using the real data in §6, plus one idea for screen 7
(compare). Note any place where the data above does not give the screen what it needs — that
feedback goes to the M06 work package.
