# S17 plan review (reviewer, 2026-11-13) of R1, R2, R4 and the [architecture] table
R1 split-validation-report: approve. Check at R1: `mkdocs build --strict` (docs-site/api/validation.md:3,5 point
mkdocstrings at validation.ValidationReport / Check, which become aliases; site.yml:52 runs it on every push).
scripts/test_impact_runtime.py:191 maps classes to modules by __module__: the map goes stale after R1 (D12 fallback covers S17).
R2 split-revision-edits: approve. tests/test_t08_w2_unsupported.py:150 patches `local.apply_edits`: the retarget at
local.py:103 must stay `from ...revision_edits import apply_edits` (by name). New module docstring names both halves
(edits and diffs); transactions.py:24 docstring goes stale.
R4: approve with rename binder_shared -> binding_common (applied). New file imports `from openflowsheet.messages import
audit` as a module (audit.auditor is rebound at run time, audit.py:53).
Table: approve with changes: 11 recorded violations listed in the table (applied); jobs forbid narrowed to executor,
worker, runner (applied); added forbid engine -> {store, authz} (applied).
Risks: (1) gate reads config and plan at --base: the config/plan commit must be the split step's parent, base = that
commit. (2) re-derive expected arch numbers with `codehealth arch` before each split in the order actually used.
(3) violations keyed by module pair: the two permanent ones absorb new imports silently. (4) scope application/ only:
cycles through studies/ invisible (validation.py:454-455). (5) restructure fix a3401585: re-pin needed.
