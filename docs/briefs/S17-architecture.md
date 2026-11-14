# S17 architecture pass: import structure, ratchet, splits, interface candidates

Design lane (architect), 2026-11-13. Measured at wp/S17 48dd64c3 with cce-code-health efdab0a4 (the pin), on a
scratch copy outside the tree. Files beside this note: `architecture-table.toml` (exact `[architecture]` text, validated)
and four draft plans `restructure-split-*.toml`. Governing rules: docs/S17_RULES.md, D12, D18, D19.

## 0. Decisions

1. Ratchet: `cycle_depth = 4` (module level), `type_checking = false`, one total-order `layers` rule stating the target
   architecture, one `forbid` rule for the transports. It records 11 violations and 1 cycle (24 modules, 83 edges).
2. Consequence (load-bearing): the gate keeps cycle edges strict even in restructure mode (architecture.py:30-34,
   `ratchet`). Moving name N from module O to a new module X makes O import X (the required re-export), so X lies on
   a cycle exactly when something X imports reaches O. In S17 a split may therefore only extract DOWNWARD (X imports
   nothing that reaches O); cycles fall when the low importers of O are retargeted to X. Moving high-level code up
   needs the old path dropped, which is D19's package.
3. Five steps, ranked: R1 validation_report, R2 revision_edits, R3 revision_binding to model_signatures and
   model_builders, R4 binding_common, R5 `_defect` to jobs/runner (refactor mode, no plan). Violations 11 -> 2, cycle
   edges 83 -> 6 (simulated per step; R1 confirmed with the tool on a scratch copy).
4. Blocker found: `restructure._binders` (restructure.py:106) crashes on any top-level function with a keyword-only
   parameter without default (`kw_defaults` holds None). 22 statements in 9 application files trigger it, among them
   authz.py and binding.py, so R1 and R4 crash the restructure gate until the tool is fixed and re-pinned (WO-B).
5. Every restructure step is debt-neutral (file debt is the sum of function debts, report.py:71; file smells feed only
   `health`). It is gated without `--require-gain` and logged `--result accepted-neutral`.

## 1. Current structure of application/

**Layers as they are.** The module-level (top-of-file) import graph is acyclic. Grouped by what imports what:

| group | modules (top-level fan-in / fan-out within application) |
| --- | --- |
| surfaces | cli (0/2, plus 13 lazy), serving (0/4), bindings.http/mcp/web (via operations, contract, types, projection) |
| facade | local (1/18, the widest fan-out), transactions (2/3; its K06 `Application` lazily imports local) |
| services | jobs.executor (1/6), jobs.worker, jobs.runner (2/10), admission (2/6), stream_table, stream_table_format, capabilities, operations |
| revision engine | validation (6/0 top-level, 7 more inside functions), revision_routes, revision_run (5/6), revision_continuation, replacement, trust_region_parent, structure_index, coupled_run, binding (5/0), revision_binding (12/1), column_binding, thermal_binding |
| persistence | store (7/3), authz (2/3) |
| vocabulary | types (14/2), contract (7/1), projection (4/1) |
| foundation | policies, revisions, jobs.model, jobs.interrupt (no application imports at run time) |

**Cycles.** With function-level imports counted (the tool reads every nesting level), 24 of 39 modules form one
strongly connected component with 83 edges. Every cycle closes through one of 23 function-level imports (cli excluded).
Removing the four lazy imports validation -> {binding, revision_binding, revision_routes, revision_run} and
transactions -> local leaves three small cycles: {types, contract, projection, validation}, {binding, revision_binding,
column_binding, thermal_binding}, {jobs.executor, jobs.worker}.

**Cohesion problems that matter** (each is the root of a cycle):

- C1 validation.py is two modules. Its report vocabulary (Task, ValidationStatus, Stage, Result, EvidenceClass, Check,
  ValidationReport, utc_timestamp; validation.py:35-164) is imported at module level by the bottom of the package
  (types.py:47, store.py:55, authz.py:54), while `validate` imports the engine inside functions (validation.py:453
  REVISION_ROUTES, :595 binding, :600 revision_binding, :604 revision_run.traced_analysis, :1055 projection). This
  pulls the whole package into one cycle: 50 of the 83 edges go when only the vocabulary moves.
- C2 transactions.py mixes the pure edit and diff algebra (transactions.py:81-273) with K06's facade over
  LocalApplication (RevisionStoreView :274, Application :338, lazy `import LocalApplication` :348). Its importers use
  only the algebra (local.py:103; revision_continuation.py:42).
- C3 revision_binding.py (2131 lines) holds three concerns: the unit-model signature catalogue and pin readers
  (ModelSignature :234, pins and encodings :206-630, thermal signatures :1501-1545, MODEL_BASES :1613), the builder
  catalogue (builders :695-1500, MODEL_BUILDERS :1642) and the binder (RevisionBinding :155, providers :1691-1957,
  bind_revision_flowsheet :1958). Its plugins import it at module level, thermal_binding.py:34-48 with 9 private
  names, while it imports them inside functions (revision_binding.py:1111, :1554).
- C4 the legacy binder owns the vocabulary both binders share: revision_binding.py:34 imports Unbound and
  `_column_owners` from binding.py, and binding.py:344 calls bind_revision_flowsheet.
- C5 jobs.worker imports a private helper of the executor that spawns it (worker.py:227 `executor._defect`;
  executor.py:59 imports worker). `_defect` builds a runner `WorkerResult` (executor.py:218).
- C6 types.py:1392 raises contract.ApplicationError, and contract.py:20 imports ApiError from types (D19 item D3).

Co-change evidence (s17-coupling.json): contract.py with operations.py, degree 0.77; admission.py with jobs/runner.py,
0.57; application with application/jobs, 46 shared commits. These are interface questions (section 6), not splits.

## 2. The `[architecture]` table (ratchet)

Exact text: `architecture-table.toml`, appended to `.codehealth/config.toml` by the orchestrator in one config commit.
It is an edit, not an added file, so it may go in now (D12) and ratchets work orders 3 to 8 as well.

- **Why a total order.** application/ is flat, and a layer entry matches one dotted prefix, so a group of sibling
  modules cannot share a layer. Rejected: six `forbid` rules expressing group layering (about 120 entries, and each new
  module edits several lists); `cycle_depth = 2` (every application module collapses to one node, the cycle check
  becomes vacuous since only in-scope files are read); no layers (cycles alone miss an upward import that does not
  yet close a cycle). The cost of a total order: a future import between two unrelated modules may need a reorder,
  done as a reviewed config commit.
- **Order** (top to bottom): cli, serving, bindings | transactions, local | jobs.executor, jobs.worker, jobs.runner,
  admission, stream_table_format, stream_table, capabilities, operations | replacement, trust_region_parent,
  validation, revision_routes, revision_run, revision_continuation, structure_index, coupled_run, binding,
  revision_binding, column_binding, thermal_binding | authz, store | projection, contract, types | policies, revisions,
  jobs.interrupt, jobs.model. Validation sits in the engine and transactions above local on purpose: the order
  states the target, so the recorded violations are exactly what R1 to R5 remove.
- **Recorded violations (11)**: types -> validation, store -> validation, authz -> validation (R1); local ->
  transactions, revision_continuation -> transactions (R2); column_binding -> revision_binding, thermal_binding ->
  revision_binding (R3); revision_binding -> binding (R4); jobs.worker -> jobs.executor (R5); types -> contract and
  revision_run -> validation (stay; D19 items D3, D4).
- **forbid `transports-through-operations`**: bindings may not import the facade, services other than operations,
  the engine, persistence, cli or serving. Grounded in bindings/__init__.py:1-3 ("each reads operations.OPERATIONS
  and goes through operations.dispatch, and adds nothing"). Zero violations today.
- **New modules.** The orchestrator adds each split's modules in the config commit before its step (the gate reads
  the config at the base; the entry draws a "matches no module" warning, not a failure, until the step lands):
  validation_report and model_signatures after jobs.model; revision_edits then binding_common just before projection;
  model_builders between revision_binding and column_binding. All but validation_report also join the transports
  rule's `to` list. A module left out of the order is ignored by the layer rule (cycles still apply).

## 3. Splits (ranked by value; execution order R1 to R5)

**Mechanics common to R1 to R4** (the reviewer checks each):
- One commit per split: create the new file(s), move the definitions verbatim in their original order with the
  `#:` comments directly above them, add the re-exports, retarget only the importers listed, drop imports ruff
  reports unused. The new file gets a module docstring and `from __future__ import annotations`, and NO `__all__`
  (its strings would break the literals multiset; docstrings are exempt, gate.py:213).
- Re-export form in the old module, inside its import block: `from openflowsheet.application.<new> import (Name as
  Name, ...)` for every moved public name, and for every moved private name that any file in src/, tests/,
  benchmarks/ or scripts/ imports from the old module or reads as `old_module.name`. The same-name alias satisfies
  ruff F401 and mypy, and the gate accepts it as a re-export (restructure.py:125). Never touch an old `__all__` and
  never remove an import whose name it lists.
- Lazy imports move with their function unchanged. No call that constructs a moved class moves unless listed.
- Only the importers named below are retargeted; all others keep the old path until D19 drops the re-exports.
- Gate: `codehealth gate --mode restructure --plan .codehealth/restructure/<id>.toml --base <last accepted>
  --ref-base MB`, no `--require-gain`. The tests tier falls back to the full suite (about 20 min). Commit
  `restructure(application/<old>): <what>`, trailers `Codehealth-Class: restructure`, `Codehealth-Recipe: split`,
  `Codehealth-Debt: X -> X`. Log `codehealth log ... --result accepted-neutral --reason "<id>: move, debt unchanged"`.

**R1 split-validation-report** (validation.py -> validation_report.py; requires WO-B). Moves the 8 public names
Task, ValidationStatus (validation.py:35-36), utc_timestamp (:60-64), Stage, Result, EvidenceClass (:75-88), Check
(:91-128), ValidationReport (:131-164); 88 lines, no private names; their closure has no application import. New file
imports Mapping, dataclass, field, Any, Literal. Retarget types.py:47, store.py:55 (and its comment at :54),
authz.py:54. Effect: violations 11 -> 8, cycle edges 83 -> 33, cycles of 11, 4 and 2 modules. Verified on a scratch
copy: `codehealth arch` gives exactly these numbers; `public_api_problems` returns [] (with the WO-B workaround) and
names the omission when one new_public entry is dropped; string-literal multiset unchanged; all application modules
import; `types.ValidationReport is validation.ValidationReport`. Risks: tests/test_t08_w2_unsupported.py:111 patches
`validation.ValidationReport`; it still works because every construction stays in validation.py (keep it so).
Tests import 13 names from validation; all stay bound. Importing types no longer imports validation (nothing in src
reads `__module__`, `__qualname__` or pickles these classes; grep of application/ is empty).

**R2 split-revision-edits** (transactions.py -> revision_edits.py; requires R1, else the new module joins the large
cycle, simulated +2 edges). Moves EditPathError, json_pointer, apply_edits, semantic_diff, ELEMENT_MEMBERS,
element_diff, revision_diff and private _apply, _by_id, _item_paths (transactions.py:81-273, 169 lines; imports
revisions.CONTENT_HASH_EXCLUDED and types DiffElement, DiffMember, Edit, SemanticDiff). `Operation`,
RevisionStoreView, Application stay. Retarget local.py:103 and revision_continuation.py:42. Effect: violations 8 -> 6,
edges 33 -> 14. Risks: none patched in tests; tests' 7 imported names stay bound.

**R3 split-revision-binding** (revision_binding.py -> model_signatures.py + model_builders.py; must follow WO4).
model_signatures = closure, over top-level Name references, of its 17 public names (plan file) plus every name
column_binding and thermal_binding import from revision_binding: 72 names, 598 lines at 48dd64c3, no application
import. model_builders = closure of MODEL_BUILDERS, resolve_surrogate, SurrogateResolver minus model_signatures: 31
names, 544 lines; it imports model_signatures at top and column_binding, thermal_binding lazily (the statements at
revision_binding.py:1111 and :1554 move inside `_syn001_column` and `_thermal_builder`). Recompute both closures at
the plan's base after WO4; STOP and report if either closure reaches RevisionBinding, bind_revision_flowsheet,
provider_for, basis_provider, SELECTABLE_BASES, `_CONTEXT` or Unbound. Retarget column_binding.py:17 and
thermal_binding.py:34 to model_signatures (in the same commit, or model_builders closes a cycle). Re-export also
`_columns` and `_COLUMN` (imported by tests). Stay: `_CONTEXT`, `_basis_refusal`, `_SAME_FUNCTION`, importlib (all
read by tests). Effect: violations 6 -> 4, edges 14 -> 10; revision_binding about 1000 lines. Risks: tests patch
`revision_binding.bind_revision_flowsheet` (stays) and setitem into MODEL_BUILDERS, MODEL_BASES (same objects).

**R4 split-binder-shared** (binding.py -> binding_common.py; requires R1 and WO-B). Moves Unbound, HINT_LIMIT,
refusal_code and private `_column_owners` (binding.py:264-305, :1261-1279; 53 lines). Retarget revision_binding.py:34
only. Unbound's lazy `projection` import moves with it; `sys._getframe(2)` reads the constructing caller's module, so
the MSG audit sees the same producers. Effect: violations 4 -> 3, edges 10 -> 8. It also lets the legacy binder be
retired later without touching the revision binder (D19 item D5).

**R5 `_defect` to jobs/runner.py** (refactor mode, no plan). Move executor.py:218-232 beside WorkerResult; executor
imports it from runner (keeps `executor._defect` for tests/test_t07_w4e_error_mapping.py:35); worker.py:227 imports it
from runner at the same lazy position. The worker then no longer imports jobs.executor (its body defines classes,
a logger and constants; state that in the commit, playbook rule 10). Gate `--no-gain`. Effect: 3 -> 2, 8 -> 6.

**Wait for D19 (not S17):** local.py (a class split changes LocalApplication's API entry, its bases and members,
gate.py:255-263; LCOM4 = 4 is three constructors plus `__enter__`, measured: 74 of 77 methods share one state
cluster); types.py (2127 lines, debt 1.0, declarative; moving about 100 public names should happen once, with their
final names); store.py, cli.py, contract.py/operations.py (interface shape); revision_run.py (its last cycle with
validation needs D4).

## 4. Work orders

- WO-A (orchestrator, now): append architecture-table.toml. Accept: `config --check` 0 problems; `arch` 39 files, the
  11 listed violations, 1 cycle 24 nodes 83 edges, 0 warnings. Re-run after WO8: identities unchanged, else stop.
- WO-B (cce-code-health session): `_binders` must skip None in `kw_defaults`; add a tool test with `def f(*, a): ...`;
  re-pin. Accept: `_binders` over every top-level statement of application/*.py raises nothing (today 22 raise).
- WO-C (orchestrator, after WO8 accepted and a reviewer pass on the plans): set approved_by, commit the four plans
  under `.codehealth/restructure/`; add `gate.sh --restructure <plan> <last accepted>` (args of section 3).
- WO-R1 to WO-R5 (engineer, one commit each, in order; R3 and R5 may run before R1 if WO-B lags; R2 and R4 never
  before R1). Each preceded by the orchestrator's layer-entry config commit (section 2).

## 5. Verification gates (numbers fixed before the runs)

| gate | criterion |
| --- | --- |
| every step | restructure gate exit 0: tiers ruff, mypy, tests (full suite), f0, mcp_digest; static plan, public API, literals, architecture; debt not higher. R5: refactor gate `--no-gain` exit 0 |
| every step | moved-definition identity: for each moved name, `ast.dump` of its top-level statement at base (old file) equals that at head (new file); `git diff --stat` lists only the plan's files and the named importers |
| after R1 / R2 / R3 / R4 / R5 | `codehealth arch`: violations 8 / 6 / 4 / 3 / 2; cycle edges 33 / 14 / 10 / 8 / 6; 0 new identities |
| campaign end | remaining cycles exactly {contract, types} and {revision_routes, revision_run, validation}; violations exactly types -> contract, revision_run -> validation |

A step whose numbers differ from the row is a miss: reset to the last accepted commit and report.

## 6. Interface-redesign candidates for the D19 package (input, no ADR text)

- D1 One application, one Operation. Now: `contract.Application` Protocol (contract.py:97, plan §2.1), K06
  `transactions.Application` and RevisionStoreView (transactions.py:338, :274), LocalApplication (local.py:172); and
  two public `Operation`s (transactions.py:57 alias of EditOperation; operations.py:99). Shape: LocalApplication
  implements the Protocol; retire the K06 facade and the alias. Touches: ADR 0019 D1, 3 test imports, docs.
- D2 LocalApplication breadth: 77 methods, 2322 lines, 18 module-level application imports. Shape: per-family
  services (revisions and edits, validation and admission, jobs, artifacts and stream tables, audit and authz,
  capabilities) composed by a thin facade; OPERATIONS binds each operation to its service. Touches: Python API, 88
  test files, operations table, MCP digest if names change.
- D3 Error vocabulary in one module: ApiErrorCode, ApiError (types.py:70, :262), ApplicationError, api_error
  (contract.py:50, :75), SolveFailedError (types.py:1312), validation's error constructors (validation.py:167-193).
  Removes the types/contract cycle. Touches: error schema (§2.2), MSG audit (api_error observes its caller), MCP digest.
- D4 Validator placement: split document checks (schema, dimensions, connectivity, components) from binder-backed
  stages; the run path consumes a stage result instead of calling `validate` (revision_run.py:381). Removes the last
  engine cycle. Touches: `validation.validate` path (32 test imports, cli, admission, local), F0 report identity.
- D5 Legacy binder's public surface: Binding, bind_revision, bind_revision_or_reason, legacy_admission, revision_probe
  (tests import Binding 33x, bind_revision_or_reason 23x). Decide whether the legacy route stays supported.
  Touches: route selection semantics (design lane), F0 corpus, replay identity.
- D6 Builder plugin API: make the pin readers and thermal signatures public in model_signatures and register builders
  in a table instead of lazy-import dispatch; tests stop importing privates (`_CONTEXT`, `_columns`, `_COLUMN`,
  `_basis_refusal`, `_defect`, `_declared_default`). Touches: MODEL_BUILDERS shape, tests.
- D7 Package layout: subpackages by layer so the ratchet becomes about six prefix entries, dropping every S17
  re-export at once. Keep bindings/ in place (its descriptions/ path is frozen). Touches: every import path, docs
  (51 lines in docs/ and docs/adr/ name validation, binding, revision_binding or transactions alone), tests,
  test-impact map rebuild (about 70 min).
- D8 Operation declaration once: contract.py's Protocols (:97, :157, :181) and operations.OPERATIONS (:352) co-change
  (0.77). Shape: one declaration per operation (types, transports, handler) from which Protocol and bindings derive.
  Touches: §2.1 Protocol (ADR), MCP digest, HTTP routes, frozen descriptions.
- D9 Admission in the job lifecycle: admit_* (admission.py:133-470) used by local.py:45 and jobs/runner.py:85, co-change
  0.57. Shape: jobs/admission.py or an admission value object the runner consumes. Touches: module path, tests.
- D10 CLI as a fourth transport: cli.py lazily imports 13 application modules; HTTP and MCP go through
  operations.dispatch, the CLI does not. Shape: operation commands dispatch through OPERATIONS and obey the transports
  rule; serve and reproduce stay administrative. Touches: CLI tests and outputs, evidence scripts, docs.

## 7. Risks and open questions (each with a default)

- Q1 (fact) WO-B timing. Default: run R3 and R5 first if the fix is not pinned when WO8 ends; R1, R2, R4 wait.
- Q2 (fact) WO4 may change revision_binding's private set. Default: recompute R3's closures at the plan base; the
  public lists cannot change under refactor mode; stop on the conditions in R3.
- Q3 (preference) Module names validation_report, revision_edits, model_signatures, model_builders, binding_common.
  Default: these; D19 may rename them with the rest.
- Q4 (preference) utc_timestamp in validation_report (store and audit stamps import it from there). Default: yes;
  a separate timestamps module is a second new file for one function. Revisit in D19 (D3, D7).
- Q5 (preference) Retarget only cycle-relevant importers. Default: yes, smaller diffs; D19 retargets globally.
- Q6 (preference) Total order versus forbid-group layering. Default: total order (section 2).
- Q7 (fact) Hidden import-order dependence: code that relies on validation (R1) or jobs.executor (R5) being loaded as
  a side effect. Default: the full-suite tier decides; a failure is a gate-fail, reset, report.
- Q8 (preference) Commit the table now (ratchets WO3 to WO8) or with the plans. Default: now.
- Not decided here: whether the legacy binder survives (D5) and any change to frozen §2.1/§2.2 items; both go to the
  D19 ADR and to Frank.
