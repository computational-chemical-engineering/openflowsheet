# S17 architecture pass: split plans (S17, bitwise) and interface-redesign candidates (next package)

You are the design-lane architect for OpenFlowsheet. Do not spawn sub-agents yourself. Do not edit, commit or create
anything inside the repository tree or the worktree: an engineer is refactoring `coupled_run.py` there right now, and
any new file in the tree breaks its test selection (S17 D12). Write your outputs only to
`/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/` (create it). Read freely in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17` (branch `wp/S17`).

## Context (established; do not re-derive)

- S17 is a code-health campaign on `src/openflowsheet/application/`. Rules: `docs/S17_RULES.md`; decisions
  `docs/S17_DECISIONS.md` (read D12, D18, D19 at the end); playbook `.codehealth/playbook.md`.
- Function-level refactors (extract helpers, same module) have cut debt 855.0 -> 683.5 and continue in work orders 3
  to 8 (coupled_run.py, revision_binding.py, jobs/model.py, transactions.py, jobs/executor.py, jobs/runner.py,
  validation.py). Private helper names will change during that; public names will not.
- D18 (Frank): module splits happen in S17 after those work orders, as `codehealth gate --mode restructure --plan
  .codehealth/restructure/<id>.toml`. Plan fields: `id`, `approved_by`, `reason`, `new_files`, `new_public`. Limits:
  only files under `src/openflowsheet/application/`; every old import path stays valid as a re-export; no public name
  renamed or removed; behaviour bitwise. Tool doc:
  `/home/eajfpeters/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md` ("Restructure") and
  the tool's README/docs for `[architecture]` rules (`layers`, `forbid`, cycles) and `codehealth arch`.
- D19 (Frank): outward-facing interfaces (CLI, Python `LocalApplication`, HTTP/MCP/web bindings in
  `application/bindings/`, job model, public names) may be renamed and restructured, with no compatibility shims,
  in a separate package after S17, through a design-lane ADR (plan §2.1/§2.2 interface freeze,
  `docs/implementation-plan.md` line 55).
- Evidence already computed (JSON in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/runs/`):
  `s17-coupling.json` (`codehealth coupling --depth 4 --since 2026-06-01`: top file pairs contract.py with
  operations.py, degree 0.77; admission.py with jobs/runner.py, 0.57, cross-module; module pair application with
  application/jobs, 46 shared commits). Largest files (NLOC, debt, max LCOM4): local.py 1739, 37.7, 4
  (`LocalApplication`, 77 methods, LCOM4 4); revision_binding.py 1553, 85.4, 5; types.py 1531, 1.0, 2;
  revision_run.py 1092, 55.1; store.py 1062, 5.5, 3; binding.py 944; coupled_run.py 942; jobs/runner.py 940;
  validation.py 897; stream_table.py 869. No `[architecture]` table exists yet in `.codehealth/config.toml`.
  Tool: `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth` (`arch --ref`, `coupling`, `scan`).

## Deliverables (in the design directory)

1. `S17-architecture.md`, at most 250 lines:
   a. The current dependency structure of `application/`: layers as they actually are (import graph), import cycles,
      and the 3 to 6 cohesion problems that matter most, each with file:line evidence.
   b. A proposed `[architecture]` table for `.codehealth/config.toml` (layers, forbid rules) that the CURRENT code
      satisfies or that records existing violations explicitly, so it works as a ratchet from now on. Check it
      against the tool's documented syntax.
   c. Split proposals, ranked by value: for each, the target file, the new files, which names move (public and
      private), the reason (cohesion, coupling, size, with evidence), the re-exports left in the old module, and the
      risk (import cycles, lazy imports, monkeypatch targets in tests: grep `tests/` for `monkeypatch.setattr` and
      `mock.patch` on the moving names, since a re-export breaks patching the old path). Prefer few, large-value
      splits (3 to 5). Say which splits should wait for the interface package instead.
   d. Interface-redesign candidates for the next package (D19), at most 10, each: the current interface, the problem
      with evidence, the proposed shape, and what it touches (schemas, MCP digest, fixtures, docs, frozen §2.1/§2.2
      items). No ADR text yet.
2. One draft plan per proposed split: `restructure-<id>.toml`, with `approved_by = "PENDING"` (the orchestrator sets
   it after review), `id`, `reason`, `new_files`, `new_public`, in the tool's documented format.

## Report (about 25 lines)

The paths written, the ranked splits in one line each, the `[architecture]` table's summary, and anything you could
not settle. Measured facts only; mark guesses as guesses.
