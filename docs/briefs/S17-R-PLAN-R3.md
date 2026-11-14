# S17 plan review: split R3 (revision_binding.py -> model_signatures.py + model_builders.py)

You are the design-lane reviewer. Read-only: write nothing in the repository tree or the worktree, commit nothing.
Do not spawn sub-agents yourself. An engineer is working in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17` (branch `wp/S17`) on validation.py; read the code at
commit e3a36046 with `git show e3a36046:<path>` (the files R3 touches do not change before the split).

Inputs in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/`:
- `restructure-split-revision-binding.toml` (the plan, recomputed at e3a36046, with a comment block listing the moved
  names, re-exports, lazy imports that move, retargets, config edit, risks and the architect's measurements);
- `split_closure.py` (the closure script) and `S17-architecture.md` section 3 "R3" (around line 137).
The plan review of R1, R2, R4 and the table is in `../runs/s17-review-plans.md` (same questions; R3 was deferred
until work order 4 had refactored revision_binding.py).

Fixed limits (Frank's delegation, `docs/S17_DECISIONS.md` D18): only files under `src/openflowsheet/application/`;
every old import path stays valid as a re-export; no public name renamed or removed; behaviour bitwise. Planned order:
R1, R2, R3, R4, R5.

Questions:
1. Cohesion: do the moved names form one concept a reader would look for under each new module's name? Anything moved
   that belongs with what stays, or left behind that belongs with what moves (the architect left
   `_c1_reactor_surrogate_of` with the binder by the closure rule)?
2. Safety: lazy imports moved into `_syn001_column` and `_thermal_builder`; `monkeypatch.setattr` / `mock.patch` /
   `setitem` targets in `tests/` naming the old path of a moved name (a re-export makes patching the old path a silent
   no-op; the architect names tests/test_t07_w5a_inspection.py:133 and tests/test_m04_wo7_surrogate_unit.py:317);
   `__all__`; `__module__` or qualified names recorded in fixtures, digests, evidence or `scripts/` (grep for
   `openflowsheet.application.revision_binding.`); import-time side effects and registration order of the builder
   catalogue.
3. Is the claimed arch effect plausible (spot-check one or two edges)?
4. Module names: clear and consistent with the package?
5. The architect's defaults: no re-export of the five thermal-only privates; model_builders joins the
   `engine-not-persistence` rule's `from` list; stale docstrings fixed in a later commit. Agree or not.

Output, at most 30 lines: `R3 | approve / approve-with-changes / reject | reason`, the exact changes for
approve-with-changes, then at most 5 lines of risks the architect missed. Quote file:line for every concern.
