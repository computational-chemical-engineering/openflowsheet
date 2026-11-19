# S19 review R-W4-PR-1b+2 (reviewer, 2026-11-19)

Read: diffs 272011be..dcd1b9a4..53484cf0..d65497b4 (wp/S19-pr1b) and 1497bcf9..c98e8662..82ad61ec (wp/S19-pr2);
briefs S19-W4-PR-1b.md, S19-W4-PR-2.md; playbook rules 7, 12 and the parameter-object row. One AST check run (no
bare read of the 21 parameter names left in `_solve_region` at 82ad61ec; no module-level name collides with them).
Not examined: the gate logs, the touched tests' assertions beyond the adapt hunks, `_region`'s unchanged lines.

## PR-1b (executor.py `_PlanRun`)

Q1 identity: holds, call by call. Every frame value is the plan's at 272011be: execute_plan passed all seven
down positionally through `_run_step`, `_solve_eo`, `_solve_revision_region`, so `_warm_start`'s candidate and the
`revision_source` of the `_eo_recovery` calls at `_solve_eo`, `_solve_revision_region` and `_warm_start` were the
plan's; `_converge`'s (default None) is restored by `replace(ctx, revision_continuation=None)` (executor.py:602),
and is unread there anyway (the tear path is SYN-001's, R3 `not_revision_built` precedes R4; the two flowsheet
classes are unrelated). `_region`, `_sequential_restart` read only flowsheet/spec/policy/run, as their old
parameters. execute_plan rebinds none of the seven after building ctx. The three new locals (`candidate`, `source`,
the cast) are field reads before the first event. No event, counter or StepResult field moved.
Q2 red adapt: call form only. Old (step, region=None, flowsheet=None, spec=None, policy, run=None, spent=None, {},
0, revision_source=None) maps one-to-one onto the new frame plus (step, None, None, {}, 0); no assertion touched.
The rrc timer wraps the same function, called positionally, and `args[0].flowsheet` is the object `args[2]` was.
Ruling: accept the red-commit form for a call adaptation (failing ids named, bisect with `--first-parent`).
Q3: sound. The cast is guarded by `_solve_eo`'s only dispatch over the two-member `Flowsheet` union; it is a
static-only hole for a hypothetical second caller (an `assert isinstance` would check it; not required). The
`_evaluates` widening passes rule 12: the metering invariant is its runtime `PropertyMeter` check, not the type.
Q4 ruling: fields stay. They are per-run constants supplied once; as arguments they would be threaded four to five
hops again, which is the debt the frame removes; the parameter-object when-not row does not apply.

Verdicts: A dcd1b9a4 merge; B 53484cf0 merge after fix 2; C d65497b4 merge after fix 1.
1. fix, docstring/comment only (new no-gain commit): executor.py:196 ("each as `execute_plan` received it"),
   :934 ("from the plan's `revision_continuation`") and :1004 ("R4: the plan's source") are untrue on the merged
   path, where ctx carries None; say so once (e.g. in `_PlanRun`'s docstring: `_converge` runs a merged region's
   edge 3 with none). Rewrite the :600 comment to state its reason (the tear path is SYN-001's, so edge 3 never reads
   a continuation there) instead of "(as at 272011be)".
2. fix, message only (tree identical, gate evidence holds; precedent R-W3-G1N-4 fix 1): B is gated `--mode step`
   but keeps the abandoned `interface(...)` subject and has no `Codehealth-Class/Recipe/Debt` trailers
   (S19_RULES Git); its message also carries a superseded paragraph. Reword as `refactor(orchestrator/executor.py)`
   with `parameter-object`, `51.2 -> 16.0`; rebase C onto it.
3. note: C's message claims AST identity with 7d54df32 (pre-fix B); its parent is 53484cf0. The diff is docstrings
   only, so the claim holds against the real parent; correct the hash if C is rewritten for fix 2.

## PR-2 (region.py `_RegionCall`)

Q5: holds. All 21 fields in `_solve_region`'s order with its defaults; solve_region passes all 21 by keyword, so
the defaults are never used. The body rebinds none of the 21 names, so every `call.x` reads what `x` read. The
constructor (keywords only, no `__post_init__`) cannot raise, so the recovery-without-compiler ValueError is still
first and the `_KernelRefusedError` handler sees the same exceptions.
Q6 ruling: accept; only the call form of the two spies changes; the private annotation is fine in a test that
already patches `_solve_region`.
Verdicts: A c98e8662 merge; B 82ad61ec merge. Note: the 21-name list is still written three times (solve_region's
signature, the `_RegionCall(...)` call, its fields), as before; the duplication smell is gone from the tool, not the
code. When the legacy ruling frees solve_region, let it take the `_RegionCall` and drop the duplicated defaults.

Overall: PR-1b merge after fixes 1-2 (no code change); PR-2 merge.
