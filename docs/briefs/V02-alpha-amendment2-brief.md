# Design-lane ruling round: V02 alpha RC findings (Amendment 2)

One batched round (CLAUDE.md "Agent budget"). Rule each item; write rulings, not code. Branch `wp/V02-alpha-gate`
@ `4d591c7`, worktree `.claude/worktrees/alpha-gate`. Spec: `docs/derivations/V02-alpha-release-spec.md` (§5.2 MR-11
l.211, §8.2 step table l.650–675, §10 A39 l.836 and A43 l.840, Q5 l.944, Amendment 1 §17 l.1029). RC record:
`docs/v02-alpha-rc-record.md` (Failures l.121). Build log: `docs/design/V02-alpha-build-decisions.md` (B-WO10-6
l.108, B-WO10-10 l.134). `C_α` = `e0e198e`. M07a manifest is `implemented`: 35 pass, 2 fail (A39, A43), 6 unsupported
(A52 (c), A60–A64 await the verdicts and WO-11). §6.3 requires M07a's manifest `tested` before the `verdict` agent runs.

**F1 (A39, step 10; spec Q5).** T08.A34 (T08 spec l.482): "every certificate the RC job emits carries the [A08]
regularity evidence … and the [A09] shared-provider qualification on exactly the prefixed energy checks (T06 A33's
rule)". T06 Amendment 4 A4.6: the qualified ids are the checks with prefixes `energy_balance.`, `phase_admissibility.`,
`independent_split.` whose result is `pass` or `fail`. Measured at `C_α`: 77 certificates audited, 72 clean (steps
2, 6, 8; steps 4–5 clean on CI). The 5 coupled-route certificates of step 12 (`g12-bundles/m02-g12-0/{bundle,live,replay}`,
`g12-edges-bundles/m02-g12v3-2-{0,1}/bundle`) qualify 25 ids: the expected 21 plus `EXT-COUPLING:reactor:T`,
`EXT-COUPLING:reactor:xi` (ADR 0034 l.42: two `residual` checks per external unit), `derivative_witness.on_pattern`,
`derivative_witness.off_pattern`. None missing; [A08] present. Q5's default: V18 (b) FAIL, escalate, do not narrow.
Decide: (i) are the certificates right to qualify those 4 ids (do those checks consult the shared provider? read
`src/openflowsheet/verify/certificate.py` and `checks.py` for how `independence_qualifications` is filled), or is
that a certificate defect; (ii) if right, is extending A34/A39's expected set for coupled routes a legitimate
counterpart rule (as MR-1…MR-11 are) or a narrowing forbidden after the fact; (iii) V18 (b)'s verdict input at `C_α`
and whether step 10 must re-run.

**B-WO10-10 (A43).** `scripts/t08_rc.py`, run unchanged for steps 1–10, writes no `machine_class` into 13 records
(steps 3, 4, 10: dist, install, lock, certificates); they carry `architecture` and `github_actions`. T08.A16 judged
only `commit`, `tree_clean`, lock on campaign records. Decide what A43's "machine class" means for fresh-runner
steps (T08.A16 scope / (architecture, CI) suffices / re-run with the class recorded).

**B-WO10-6 (MR-11 input).** `benchmarks/m02/g12_real_loop.py` (frozen at `C_α`) keeps only `certificate_sha256` in a
`TemporaryDirectory`. Step 10 audited files kept by an out-of-tree wrapper that only swaps `tempfile.TemporaryDirectory`
for a kept directory. Decide: acceptable as step 12's output, or audit only the hashes the record carries (and then
whether the kept files' hashes must equal the recorded `certificate_sha256`).

## Rules
- Do not reopen ADR 0028 or the spec beyond these items. Never move a tolerance, band or classification rule
  without saying what evidence justifies it independent of the measured outcome. Do not edit production code or tests.
- Write the rulings as **§18 Amendment 2** of the spec, with markers at the amended rows, and register entries
  **R-345…R-349** (`docs/decision-register.md` on this branch). Commit on `wp/V02-alpha-gate`, named paths only; no gate.
- For each ruling state the build-lane action (re-run, regenerate manifest, test change) so an engineer can apply it.
- Report ≤ 300 words: per item the ruling in one line, V18 (b)'s status, the commit, the build-lane actions.
