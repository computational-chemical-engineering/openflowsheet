# S17 restructure: recompute split R3 (revision_binding.py) after work order 4

You are the design-lane architect. Do not spawn sub-agents yourself. Do not edit, commit or create anything inside
the repository tree or the worktree: an engineer is refactoring validation.py there now (D12, D14). Write only in
`/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/`. Read freely in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17` at commit e3a36046 (use `git show e3a36046:<path>` so the
engineer's uncommitted edits never enter your reading; revision_binding.py, column_binding.py, thermal_binding.py and
coupled_run.py will not change before the split).

## Established (do not re-derive)

- Your earlier note `design/S17-architecture.md` section 3, "R3 split-revision-binding" (around line 137), defines R3:
  model_signatures = closure over top-level Name references of its 17 public names plus every name column_binding and
  thermal_binding import from revision_binding; model_builders = closure of MODEL_BUILDERS, resolve_surrogate,
  SurrogateResolver minus model_signatures; the STOP conditions; the retargets of column_binding.py:17 and
  thermal_binding.py:34; re-exports `_columns`, `_COLUMN`; stays `_CONTEXT`, `_basis_refusal`, `_SAME_FUNCTION`,
  importlib. Draft plan: `design/restructure-split-revision-binding.toml` (names measured at 48dd64c3).
- Since then work order 4 (5a21f253..e0c43abe) and review 5's follow-up (140ce084) extracted private helpers from
  `bind_revision_flowsheet` (`_model_refusal`, `_surrogate_manifests`, `_built_instances`, `_split_key_refusal`,
  `_port_refusal`), `instance_contract` (`_require_one_keyed`) and `_unadmitted` (`_unadmitted_thermal`), and added a
  `TYPE_CHECKING` import of `PropertyMeter`. Public names did not change.
- Limits (Frank's delegation, D18): only files under `src/openflowsheet/application/`; every old import path stays
  valid as a re-export; no public name renamed or removed; behaviour bitwise; a moved name's `__module__` changes, so
  grep fixtures, `scripts/` and `tests/` (monkeypatch.setattr, mock.patch, setitem) for the old dotted path.
- `[architecture]` table in `.codehealth/config.toml` (D20): new modules get layer entries in the commit before the
  split; model_signatures after jobs.model, model_builders between revision_binding and column_binding, both in the
  transports rule's `to` list. Tool: `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth`
  (`arch`, `restructure` docs in `/home/eajfpeters/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md`).

## Deliverables

1. Recompute both closures at e3a36046 (script it; say how). Check every STOP condition; if one hits, stop and
   report it with file:line. Where do the new private helpers land, and does each land with what it calls?
2. Rewrite `design/restructure-split-revision-binding.toml` in place (approved_by stays "PENDING"), with the reason's
   numbers re-measured, and add a comment block listing the moved names per new file, the re-exports left in
   revision_binding.py, the lazy imports that move, and the retargeted imports.
3. The expected `codehealth arch` numbers after R3 alone on top of the current config (violations, cycle edges), and
   after R3 if R1 and R2 run first. Measure what you can with the tool on a scratch copy outside the repository
   (`git worktree` is not allowed; use `git archive e3a36046 | tar -x -C <scratch dir>`), mark guesses.

## Report (about 25 lines)

Paths written, closure sizes (names, lines) per new file, STOP checks, the patch/setitem risks found, the arch numbers,
anything unsettled.
