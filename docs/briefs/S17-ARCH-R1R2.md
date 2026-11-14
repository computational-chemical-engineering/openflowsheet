# S17 restructure: recompute splits R1 (validation.py) and R2 (transactions.py) after work orders 5 and 7

You are the design-lane architect. Do not spawn sub-agents yourself. Do not edit, commit or create anything inside
the repository tree or the worktree: an engineer is working there now (D12, D14). Write only in
`/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/` (scratch under `design/scratch-r1r2/`, deleted when
done). Read the code at commit f3cef5cc with `git -C /home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17 show
f3cef5cc:<path>`; for tool runs extract a copy with `git archive f3cef5cc | tar -x -C <scratch>` (no `git worktree`).

## Established (do not re-derive)

- Your earlier note `design/S17-architecture.md` section 3 defines R1 split-validation-report (validation.py ->
  validation_report.py) and R2 split-revision-edits (transactions.py -> revision_edits.py); draft plans
  `design/restructure-split-validation-report.toml` and `design/restructure-split-revision-edits.toml`, measured at
  48dd64c3. The plan review `runs/s17-review-plans.md` approved both, with checks: R1 `mkdocs build --strict`
  (docs-site/api/validation.md:3,5 point mkdocstrings at validation.ValidationReport / Check, which become aliases);
  R2: tests/test_t08_w2_unsupported.py:150 patches `local.apply_edits`, so the retarget at local.py:103 stays
  `from ...revision_edits import apply_edits` (by name); R2's new module docstring names both halves (edits, diffs);
  transactions.py's module docstring goes stale.
- Since then: work order 5 (263cbf44..cae099ae, plus 7cf38820) extracted `_apply_at`, `_ensure_member`,
  `_check_array_index` from transactions.py's `_apply`; work order 7 (e3a36046..02ce7453) extracted from validation.py
  `_static_check`, `_schema_stage`, `_dimensions_check`, `_refused_checks`, `_judged_specifications`,
  `_judged_parameters`, `_with_hint` (to be renamed `_code_with_hint` and moved after `_judged_parameters` in a
  follow-up commit before the splits; the local `schema` in `validate` becomes `schema_outcome`), and added
  `TYPE_CHECKING` imports (`ReadinessCode`, `StaticReadiness`, `UnitConversion`, `RevisionError`).
- A fact from the R3 recompute: transactions.py's `__all__` lists `Edit`, `DiffElement`, `SemanticDiff`, so their
  imports stay in transactions.py.
- R3 (revision_binding) was recomputed and approved with changes; planned split order R1, R2, R3, R4, R5.
- Limits (D18): only files under `src/openflowsheet/application/`; every old import path stays valid as a re-export;
  no public name renamed or removed; behaviour bitwise; a moved name's `__module__` changes (grep fixtures, `scripts/`,
  `tests/`, docs-site for old dotted paths; `scripts/test_impact_runtime.py:191` maps classes by `__module__`).
- The gate in restructure mode: literal multiset over all touched files, public-API check (a definition may become a
  re-export only when the new file defines it with the identical API entry), `new_public` exact, arch ratchet (D20).
  Tool `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth`; docs in
  `/home/eajfpeters/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md`. A closure script in
  the same style as `design/split_closure.py` (R3) is welcome.

## Deliverables

1. Recompute each split's move set at f3cef5cc: where each new private helper lands, and whether it lands with what it
   calls and what calls it. Stop and report if a helper would force a public name or an old path to break.
2. Rewrite both plan TOMLs in place (approved_by stays "PENDING"): numbers re-measured, a comment block listing moved
   names per file, re-exports left, lazy imports that move, retargeted imports, the config edit (layer entries:
   validation_report after jobs.model; revision_edits before projection; revision_edits in the transports rule's
   `to` list), risks.
3. On a scratch copy, apply R1 then R2 and run what you can: ruff, mypy, the gate's static checks if runnable, and
   `codehealth arch` after R1 and after R1+R2 (expected 8/33 and 6/14 in the old note; R3's recompute measured R1+R2
   at 6 violations, 4 cycles, 14 edges). Mark what you could not run.

## Report (about 25 lines)

Paths written, move-set sizes, the patch/identity risks found, the arch numbers, anything unsettled with a default.
