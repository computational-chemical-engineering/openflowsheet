# S17 plan review: architecture table and split plans R1, R2, R4 (R3 is reviewed again after work order 4)

You are the design-lane reviewer. Read-only: write nothing in the repository tree or the worktree, commit nothing.
Do not spawn sub-agents yourself. An engineer is working in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17` (branch `wp/S17`); read code there, never edit.

Inputs, all in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/`:
- `S17-architecture.md` (the architect's note: dependency structure, cycles, ranked splits R1 to R5, interface
  candidates for a later package);
- `architecture-table.toml` (a proposed `[architecture]` table for `.codehealth/config.toml`, meant as a ratchet);
- `restructure-split-validation-report.toml` (R1), `restructure-split-revision-edits.toml` (R2),
  `restructure-split-binder-shared.toml` (R4). Skip `restructure-split-revision-binding.toml` (R3): it is recomputed
  after the work order that refactors revision_binding.py.

Fixed limits for every split (Frank's delegation, `docs/S17_DECISIONS.md` D18): only files under
`src/openflowsheet/application/`; every old import path stays valid as a re-export; no public name renamed or removed;
behaviour bitwise. Splits that would need an old path dropped belong to the later interface package (D19), not here.

Questions, per plan:
1. Cohesion: do the moved names form one concept a reader would look for under the new module's name? Is anything
   moved that belongs with what stays, or left behind that belongs with what moves?
2. Safety: lazy imports inside functions, import-time side effects, module-level state, `monkeypatch.setattr` /
   `mock.patch` targets in `tests/` that name the old path of a moved name (a re-export makes patching the old path a
   silent no-op), `__all__`, pickling or qualified names recorded in fixtures, digests or evidence (a moved class's
   `__module__` changes: grep fixtures and `scripts/` for the old dotted names).
3. Is the claimed effect on layer violations and cycle edges plausible from the code? (Spot-check one or two edges.)
4. Module name: clear, and consistent with the package's naming?

For the table: does it encode a sensible target layering, does it record (not hide) the existing violations, and will
it block a new violation in later steps without blocking the planned splits?

Output, at most 40 lines: per plan `R<n> | approve / approve-with-changes / reject | reason`, with the exact changes
for approve-with-changes (names to add or remove from the move set, a new module name); the same for the table; then
at most 5 lines on risks the architect missed. Quote file:line for every concern.
