# CLAUDE.md — working rules for this repository

This repository implements the agent-native open process simulator. The work is split between two lanes — a **design lane** that specifies, decides and reviews, and a **build lane** that implements — and these rules apply to every session and every agent in either. Which model or effort level serves a lane is set in the agent definitions (`.claude/agents/`, `~/.claude/agents/`), not here.

## Authority

- `docs/blueprint-v3.1.md` is the architectural authority. Its SHA-256 is recorded in the header of `docs/implementation-plan.md`; verify it matches before acting on the blueprint.
- `docs/implementation-plan.md` (plan v1.2) is the execution authority: work packages, order, acceptance evidence, gates, and the two-lane protocol (§1.3).
- `docs/decision-register.md` indexes what was chosen, what was rejected, and why. It is not an authority in itself — the ADR it points at is — but you read the entry before changing anything it covers, and reversing a registered decision takes a new decision recorded the same way.
- `docs/design-history/` is archival. It is not a source of additional obligations.
- Do not re-plan, reopen architecture, or survey alternative technologies. A departure from the blueprint or plan requires an ADR under `docs/adr/` stating reason, affected requirements, migration impact, and acceptance evidence.

## Session start

1. Read `CLAUDE.md`, then `docs/progress.md` (if present), `docs/decision-register.md`, the latest `evidence/<package>/*/manifest.json`, and any open ADRs.
2. Run `git status` and `git log --oneline -20`. Never overwrite concurrent work.
3. Resume the next incomplete acceptance item named in `docs/progress.md`. Do not regenerate passed fixtures or restart discussions the ADRs have closed.

## The two lanes

The session runs the build lane; the design lane runs as subagents at the highest effort: `specifier` (derivations, ADRs, test specifications), `architect` (software and solver design), `reviewer` (independent review of finished work), `verdict` (decisions on evidence). State at the top of the session which lane you are working in. Older documents name the lanes after the models that once filled them — read **Fable** as the design lane and **Opus** as the build lane; the records themselves are not rewritten. The lane rule (plan §1.3):

- **If a task has no test that would catch its failure, it is a design-lane task.** If it does, it is a build-lane task, with a design-lane review whenever it touches residuals, derivatives, phase logic, scaling, certificates, or replay identity.
- **The design lane leads:** scientific semantics (units/state/zero-flow, sign conventions, reference states); all derivations (SYN-001, PTC mapping, sensitivities); the backend decision and every ADR; phase-attempt controller design; scaling and globalization policy; certificate and regularity policy; adversarial verifier tests; benchmark registration and reference-comparison verdicts.
- **The build lane leads:** repository bootstrap, packaging, CI, dependency and binary inventories, schemas and round-trip fixtures, canonicalization, application/transaction layer, CLI and Python/HTTP/MCP bindings, job lifecycle, replay bundle mechanics, unit-model implementation from design-approved equations, property-provider plumbing and caches, adapters, web shell, reference-environment acquisition, test generation for stated specifications, documentation.
- The *Lane* column of each package table in the plan is binding. The lead lane owns the branch and the evidence manifest.
- The build lane does not resolve a scientific ambiguity by choosing; it escalates to the design lane in `docs/progress.md`. The design lane does not resolve a tooling ambiguity by improvising; it delegates to the build lane with a stated acceptance test.
- Build-lane chunks inside a design-led package are delegated as subagents (worktree isolation), and the design lane reviews the result before merging.

## Agent budget (Frank, 2026-10-09)

Token usage is a constraint. These rules cut it without dropping a review, a gate, or a design-lane ruling:

- **At most 2 agents at a time.** Let running agents finish; never stop one mid-work to save tokens.
- **Never resume a large-context agent for a follow-up.** Each follow-up rereads the agent's whole context, often
  400–500k tokens. Ask a fresh design agent with a tight brief instead: the question, the measured facts, and the
  `file:line` anchors it needs.
- **Batch design-lane questions per package.** The engineer makes each open choice as an isolated, revertible commit,
  logs it in the package's build-decisions file, and carries on. One ruling round happens at a natural break, preferably
  folded into the package's single `reviewer` pass. Stop early only when a choice would change numerics, identity, or a
  frozen interface.
- **Small work orders, about 150k context per engineer.** An engineer that reaches the cap commits what is complete,
  writes where it stopped, and ends. A fresh agent continues from the commit log.
- **Sonnet for bounded items**: manifests, docs, fixture re-takes, generator-check tests, mechanical edits. Opus for
  numerics and design-adjacent code.
- **Quiet runs.** Tests and builds are free; reading their output is not. Run the gate as `scripts/gate.sh` (one
  summary line; the failing lines only on failure; full log in a file). Read a log only on failure, by `grep`/`tail`.
  Start long runs in the background and wait for the one completion notice; no polling.
- **Short reports, 200–300 words.** Full detail goes into the package's build-decisions log in the repository.
- **Unchanged:** one design-lane spec or design pass and one `reviewer` pass per package, the full gate before every
  commit, and decisions recorded in the register.

## Branch and merge discipline

- One branch per work package, named `wp/<ID>` (for example `wp/K03`). The lead lane owns it.
- Interfaces in plan §2.1 and schemas in §2.2 are frozen at the end of P01; they change only by a design-lane ADR.
- Merge to `main` only when `evidence/<ID>/<commit>/manifest.json` exists with `status: tested`. `BLOCKED` and `planned` are never merged as done.
- **Never set `reviewed` on your own package.** The design lane (`reviewer`) reviews build-lane scientific-adjacent work; the build lane reviews design-lane work for coverage, packaging, and documentation. Human numerical/process-modeling sign-off is recorded separately and is not something an agent may claim.
- Commit coherent changes with messages naming the package ID. Do not commit large binary artifacts; put them under `evidence/**/artifacts/` (ignored) and reference them by hash in the manifest.

## Scientific conduct

- No placeholder success paths. Unimplemented capabilities return explicit unsupported results.
- No relaxed checks, removed cases, or narrowed denominators to pass a gate. A failed gate stays failed and is reported as such.
- Self-generated outputs are regression fixtures, not validation. Correctness fixtures need an analytic or independent expectation.
- Residual and Jacobian paths must describe the same function at the same state. Exact property caches key on exact canonical inputs; never quantize state coordinates on the exact path.
- Distinguish `implemented`, `tested`, `reviewed`, and `released` in every manifest and report. Distinguish numerical verification from empirical validation from optimality evidence.
- Angle-bracket fields in manifest templates are never valid evidence values.

## Session end

1. Update `docs/progress.md`: completed packages, current package, **the next executable action**, blockers with evidence.
2. Ensure the evidence manifest for touched packages reflects actual status and actual commands run.
3. Commit. Leave the working tree clean or explain why not in `docs/progress.md`.

## Escalation to Frank

Stop and describe the exact blocker, with evidence and completed useful work, only when: a scientific requirement must change; rights, data, or external access are unresolved; compute exceeds existing authorization; or an irreversible external action is needed. Ordinary implementation decisions do not require permission.
