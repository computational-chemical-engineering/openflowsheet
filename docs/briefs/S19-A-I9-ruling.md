# S19 ruling A-I9 (ADR 0076 I-9): `validate_document` goes to the foundation, so `application.errors` imports nothing above itself

Design lane (`architect`, Fable 5.2), 2026-11-16. Measured at `wp/S19-w4` 486b6dbb (arch identical to the I-4 head
be115b6a). Answers brief `S19-A-I9-home.md`. Binds a new step **I-5b** and the W4 step I-9.
Authorities: ADR 0076 I-5, I-9, I-12a, "No shims", the migration rows; `S19_RULES.md`. No production code here.

## 1. Ruling

`DocumentSchemaError`, `validate_document` and `_raise_first` move from `application/types.py` to
`openflowsheet/schema_check.py` (the engineer's proposal, accepted), as a step of its own, **I-5b, before I-9**.
`ApiError.from_document` stays a classmethod of `ApiError` and, in `application/errors.py`, imports `validate_document`
from `openflowsheet.schema_check`. The place of `application.errors` in `application-layers` stays as the ADR has it:
directly below `application.types`. No layer order in the ADR changes; I-12a's `documents.py` list loses two names.

Why this home. `validate_document` is the raise-first form of `schema_errors`: the same cached `_validator`, the
same sort (`absolute_path`), the same `_pointer`; validation.py:429 already calls the order "`_raise_first`'s rule".
ADR I-5's reason ("document validation against `schemas/` is foundation") covers it word for word. The three
definitions need nothing that schema_check.py does not already import (`Draft202012Validator`, `Any`), so the move
adds no import to the foundation module and no edge between application modules. After it, `_validator` and
`_pointer` have no user outside schema_check.py (types.py:187 and :194 were the only ones): the private names that
cross from schema_check into the application go from five to four.

## 2. Rejected

| alternative | reason |
|---|---|
| I-9 as written (`errors` imports `validate_document` from `types`) | measured: 3 / 3 / 12, with a new violation `errors -> types` and a cycle `errors <-> types` (section 5); the row "removes cycle 8" is not met |
| a function-level import of `types` inside `from_document` | the tool reads imports at every nesting level (config.toml:101): same violation, same cycle |
| `errors` above `types` in the order | `types` raises `ApplicationError` and `SolveFailedError` and builds `ApiError` at run time: `types -> errors` is then the old `types -> contract` violation under a new name |
| `ApiError.from_document` becomes a function in types/documents, or stops validating | breaks the one `from_document` classmethod protocol of the typed documents, or changes behaviour; an interface change that buys nothing the move does not |
| create `application/documents.py` now (part of I-12a pulled forward), below `errors` | layering works, but one concept stays split over two packages (`schema_errors` below, `validate_document` above), `_validator` and `_pointer` must then become public for it, and I-9 becomes a two-module step with a half-filled module until I-12a |
| the three names into `application/errors.py` | a schema validator is not error vocabulary; `errors` imports the registry after I-14, which a foundation caller of `validate_document` must not need |

## 3. The moves

**I-5b** (pure move, text and docstrings byte-identical, no rename, no signature change):

| name | from (486b6dbb) | to |
|---|---|---|
| `DocumentSchemaError` (class) | application/types.py:128-135 | schema_check.py, directly below `SCHEMA_BASE` |
| `validate_document` | application/types.py:185-187 | schema_check.py, after `schema_errors` |
| `_raise_first` (stays private, same name) | application/types.py:190-194 | schema_check.py, after `validate_document` |

- schema_check.py: no new import. Its module docstring gains one sentence: "`validate_document` raises
  `DocumentSchemaError` for the first error in the same order."
- types.py: its `from openflowsheet.schema_check import (...)` block becomes `SCHEMA_BASE`, `DocumentSchemaError`,
  `_consumer_job_schema`, `_published`, `_raise_first`, `_registry`, `validate_document` (plain imports of names its
  own code uses; no `X as X` alias). `_pointer` and `_validator` leave the block. Nothing else in types.py changes:
  `_checked`, `published_schemas`, `validate_inline`, the event schema helpers and every `from_document` stay.
- Callers retargeted to `openflowsheet.schema_check`: application/cli.py:789 (`DocumentSchemaError` only;
  `validate_inline` stays from types), application/local.py:116 and :142 (`DocumentSchemaError`, `validate_document`),
  application/operations.py:66 (`DocumentSchemaError`); the tests that import either name from `application.types`
  (8 files at 486b6dbb: `git grep -lw "DocumentSchemaError\|validate_document" -- tests`). No patch target names any
  of the three (grep of `types.<name>` patterns over tests and scripts: 0 hits).
- After I-5b no module other than types.py reads the three names through `application.types`.

**I-9** (as ADR 0076 I-9, with one line fixed by this ruling): errors.py has
`from openflowsheet.schema_check import validate_document`; `ApiError.from_document` is unchanged text.
`SolveFailedError` takes `RunResult` under `if TYPE_CHECKING:` (from `application.types`; from `job_records` after
I-12a); the tool ignores that block (`type_checking = false`). errors.py imports **no** `openflowsheet.application.*`
module at run time. Its run-time imports: `sys`, `openflowsheet.messages.audit` (top), `openflowsheet.schema_check`
(top), `openflowsheet.messages.render` and `.text` (function level, as today), and `openflowsheet.registry` from I-14.
types.py imports the error names from `errors` at top level; the function-level import at types.py:1343 goes with the
cycle that was its reason (default: `ApplicationError` joins the top-level import; `errors` is loaded by then, so no
import order changes).

## 4. Layer order

- After I-5b: `application-layers` and `repo-layers` unchanged.
- After I-9 (the ADR row, unchanged): `... projection, contract, types, errors, revisions, jobs.interrupt, jobs.model,
  validation_report`; the `types -> contract` adoption line goes. `repo-layers` unchanged
  (`application -> schema_check` is downward; no forbid rule names `schema_check`).
- After I-12a (the ADR row, unchanged): `projection, contract`, the five type modules (`inspection_types`,
  `job_records`, `job_requests`, `policy_types`, `transaction_types`, order fixed by the import graph at the base),
  then `errors`, then `documents`, then the foundation four. Under this ruling `errors` and `documents` do not import
  each other and neither imports a type module, so the row's order holds without a constraint between the two.

## 5. Arch numbers (`codehealth arch --depth 4`: violations / cycles / cycle edges)

Measured on a scratch export of 486b6dbb with the import statements only (no definition moved, callers of the error
names not retargeted, so the import totals of these runs are not gate numbers):

| state | files | v / c / e | detail |
|---|---|---|---|
| base 486b6dbb | 314 | 3 / 3 / 12 | 3989 imports; as the brief |
| after I-5b | 314 | **3 / 3 / 12** | unchanged, largest cycle 4 nodes |
| after I-9 under this ruling | 315 | **2 / 2 / 10** | largest cycle 4 nodes |
| after I-9 as the ADR was written | 315 | 3 / 3 / 12 | new `errors -> types` violation, cycle `errors <-> types` (2 edges) |

After I-9 the violations are exactly `application.revision_run -> application.validation` (I-10) and
`messages.catalogue -> registry` (I-14); the cycles are `revision_routes <-> revision_run <-> validation` (4 edges,
I-10) and the messages/registry cycle (6 edges, I-14). The full retarget cannot change these: errors.py has no
out-edge into the application, and every importer of the error names sits at or above `types`. The engineer
re-derives the import total at each plan's base; a mismatch of v / c / e stops the lane.

## 6. Work orders

1. **I-5b step**, on `wp/S19-w4` from the lane tip. Row form as I-10's (interface tier, `renamed`
   `types.py:<name> = schema_check.py:<name>` for the two public names, `callers` = the three src files and the
   tests). If the tool refuses that form, split it as I-5 was (restructure plan `move-document-validation.toml`, src
   retarget in refactor mode, tests outside the gate, as 07535927 and 0ef51cc8); no alias is written, so no later
   alias-dropping step exists. Before it: the source-reading grep of `S19_RULES.md` for `application/types.py`,
   `"types.py"` and `schema_check.py` (tests/data/t07_global_state_allowlist.json names types.py; the moved code holds
   no module-level state). Acceptance: gate G1.
2. **I-9 step**, as ADR 0076 I-9 and section 3. The MSG probe test is already at 486b6dbb. Acceptance: gate G2.
3. **Docs** (orchestrator): the addenda of section 8 into ADR 0076; the ruling in `S19_DECISIONS.md` and the decision
   register; I-9's config change as its row says. I-12a's brief takes its list from addendum 3.

## 7. Gates

- **G1 (I-5b).** (a) arch 3 / 3 / 12 at base and head. (b) The three definitions are byte-identical at base
  (types.py) and head (schema_check.py): the `diff` of the extracted blocks is empty and quoted in the step message.
  (c) `git grep -nw "_validator\|_pointer" -- src/openflowsheet/application` has no hit at head.
  (d) `git grep -n "application.types import" -- src tests scripts benchmarks examples`, read with its continuation
  lines, shows no import of `DocumentSchemaError` or `validate_document`. (e) `patch_noop.py`: 0 flagged.
  (f) F0, the MCP digest and the tests as the gate runs them: identical.
- **G2 (I-9).** (a) arch 2 / 2 / 10, the two violations and two cycles of section 5 and no other. (b) No cycle and no
  violation names `application.errors`, `application.types` or `application.contract`.
  (c) `grep -n "openflowsheet.application" src/openflowsheet/application/errors.py` hits only inside the
  `if TYPE_CHECKING:` block. (d) ADR 0076's I-9 acceptance (the caller-module probe) passes before and after.
- **Falsifier of the ruling itself:** row 4 of section 5. If G2 (a) reads 3 / 3 / 12, errors.py still reaches `types`.

## 8. ADR 0076 addenda (text to record; the orchestrator adds the register number)

1. Under I-5: "Addendum (S19 W4, 2026-11-16, ruling A-I9 on Fable 5.2, `docs/briefs/S19-A-I9-ruling.md`): **I-5b.**
   `DocumentSchemaError`, `validate_document` and the private `_raise_first` (application/types.py:128, :185, :190 at
   486b6dbb) also become `openflowsheet.schema_check` names: a pure move, before I-9. Reason: they are the
   raise-first form of `schema_errors` over the same validator, order and pointer, and I-9's `application.errors`
   needs `validate_document` (`ApiError.from_document`) from below itself. Left in types.py, the I-9 step ends at 3
   violations / 3 cycles / 12 cycle edges with a new `errors -> types` violation and an `errors <-> types` cycle
   (measured at import level). `_validator` and `_pointer` are private to schema_check again. Callers:
   application.cli (lazy), application.local, application.operations, tests."
2. Under I-9: "Addendum (same ruling): `ApiError.from_document` imports `validate_document` from
   `openflowsheet.schema_check` (I-5b). `application.errors` imports no application module at run time (`RunResult`
   under `TYPE_CHECKING` only); its place in `application-layers` is as stated. Expected `codehealth arch --depth 4`:
   3 / 3 / 12 -> 2 / 2 / 10."
3. Under I-12a: "Addendum (same ruling): `documents.py` takes `published_schemas`, `validate_inline` and the schema
   helpers left in types.py (`_event_common_schema`, `_event_common_validator`, `_consumer_event_schema`, `_checked`).
   `DocumentSchemaError` and `validate_document` are not on its list (I-5b). The order of the I-12a row stands."
4. Migration table, new row after I-5: "| I-5b | interface | `renamed` (types.py: `DocumentSchemaError`,
   `validate_document` = schema_check.py, same names), `callers` (application/cli.py, local.py, operations.py; the
   tests that import either name) | none |". Recommended order: `..., I-5, I-4, I-5b, I-9, I-14, ...`. Hard
   constraints gain "I-5b before I-9". No "after:" config cell changes.

## 9. Effects

- **I-5:** done and reviewed (R-W4-1a); its commits and `i5-schema-check.toml` are not touched. It gains the sibling
  step I-5b and addendum 1. `schema_check` now owns the list form, the raise form and the error class.
- **I-12a:** `documents.py` loses `DocumentSchemaError`, `validate_document` and `_raise_first` (about 14 of its 83
  NLOC); it keeps the application's own reading: `published_schemas` with J5's consumer event schema,
  `validate_inline`, the event common validator, `_checked`. Its callers list shrinks by the importers retargeted in
  I-5b. Layer order unchanged. "I-5 before I-12a" stands.
- **I-14:** none. Its precondition, installer list and fresh-interpreter tests stand. `schema_check` imports only
  `openflowsheet.resources`, `jsonschema` and `referencing`: no path to `messages.catalogue` or the registry.
  Every importer of the error names loaded `jsonschema` through `application.types` before, so errors.py adds no
  import cost. A process that imports only `schema_check` does not install the freeze hook, as today
  (`assessment.spec`); `DocumentSchemaError` renders no catalogue text.

## 10. Risks and open questions (each with a default; none blocks I-5b or I-9)

1. *Fact.* `DocumentSchemaError.__module__` becomes `openflowsheet.schema_check`, and the frames of
   `validate_document` and `_raise_first` move files. The runner records `type(error).__name__` only. Experiment:
   `git grep -n "__module__" -- src tests scripts` read for exception types, and the gate. Default: proceed; a test
   or document that observes it is a STOP, not a retarget.
2. *Preference.* `validate_inline` has no application dependency either and could join schema_check. Not decided:
   I-9 does not need it. Default: it stays on I-12a's `documents.py` list; revisit in I-12a's brief.
3. *Preference.* Four private schema_check names are imported by the application (`_published`, `_registry`,
   `_consumer_job_schema`, `_raise_first`; five before this ruling, accepted at I-5's review). Public names for them
   are not decided here. Default: unchanged through I-12a (a pure move does not rename); a rename is an `added` row
   by its own addendum, at I-12a or I-19.
4. *Fact, outside the question.* `task_unsupported`, `nlp_solver_unavailable` and `optimization_request_missing`
   call `api_error` directly, so the caller the audit records for them changes from `application.validation` to
   `application.errors` when I-9 moves them (same frame count, an `openflowsheet.` frame). Default: proceed as the
   ADR lists them; a test that pins the old module name is a STOP for the orchestrator.
