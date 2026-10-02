# Brief — P02 Pyomo/PyNumero (ASL) harness

Repository `/home/frankp/Codes/Process Simulator`, branch `wp/P02` (already checked out; **do not run any git command** — the coordinator commits). You implement one half of work package P02: the Pyomo route of a matched two-backend composition test. The CasADi half is being written in parallel by the coordinator; stay inside your files.

## Read first, in this order

1. `CLAUDE.md` — binding working rules. Note especially: no placeholder success paths, no relaxed checks, a failed check stays failed and is reported.
2. `docs/derivations/P02-composition-spec.md` — the authority for everything you build. Read §2 (the compiled subsystem, variable and equation orderings, the closed-form Jacobian), §3 (the two callback blocks and their declared sparsities), §5 (registered states), §7 (measurement protocol), §10.1 and §10.3 (your execution notes), §10.4 (the result envelope), §11 (verdict rules). §6 is the judge's assertion catalogue: read it to understand what your output must make checkable, but **you do not implement the judge**.
3. `spikes/p02/common/` — the shared, backend-free layer, already written and committed. Use it; do not duplicate it and do not modify it. If you need something changed there, say so in your report instead of editing it.

## Your deliverables, and nothing else

- `spikes/p02/pyomo/harness.py`
- `spikes/p02/pyomo/run.sh` (executable; runs the harness in `.venv-pyomo` from the repository root)
- `spikes/p02/results/pyomo/**` — the produced result set, by running it

Do not touch any other file. In particular do not modify `benchmarks/`, `docs/`, `tests/`, `pyproject.toml`, or anything under `spikes/p02/common/` or `spikes/p02/casadi/`.

## Environment

`.venv-pyomo` exists at the repository root with pyomo 6.10.1, numpy 2.2.4, scipy 1.15.3, PyYAML 6.0.2. PyNumero's ASL library is **already built**: `AmplInterface.available()` returns True. Run things as `.venv-pyomo/bin/python ...` from the repository root, with `PYTHONPATH=.` so that `spikes.p02.common` imports. Do not install anything. Do not modify the repository environment `.venv`.

## What the harness must do

For each registered state from `spikes.p02.common.load_states()` (S1–S6, S1p, S7a, S7b), build the **L-form** of specification §2.4 as a Pyomo model with two `ExternalGreyBoxModel` blocks, expose it through `PyomoNLPWithGreyBoxBlocks`, and export:

- the residual vector in the §2.4 equation order,
- the Jacobian as canonical CSC in the §2.4 row and column order, built with `spikes.p02.common.canonical_csc` from entries keyed by `(row_id, col_id)`,
- the callback counters, the source-map example, the timings, the memory figures, the raw structure, and the second-order probe result.

Use the payload builders in `spikes.p02.common.results` (`metadata_payload`, `residual_payload`, `jacobian_payload`, `ResultWriter`) so your output has exactly the shape the judge reads. File layout is `ResultWriter("pyomo")`: `metadata.json`, `environment.json`, `states/<state_id>/residual_L.json`, `states/<state_id>/jacobian_L.json`, `callback_counts.json`, `timings.json`, `memory.json`, `second_order.json`, `source_map_example.json`, `raw_structure.json`.

### Points that decide whether this is right

1. **Grey-box wiring is settled.** Measured on this machine: `block.set_external_model(model, inputs=[...existing Vars...], outputs=[...existing Vars...])` attaches to the model's own variables — no input copies, no link constraints. Use that form. The block's `output_constraints[...]` rows then *are* the specification's `kdef_i` and `hdef_i` rows, so the assembled system is natively 17 × 17 with 60 nonzeros. If the keyword form is rejected on the full model, fall back to the block's own `inputs`/`outputs` with link constraints, implement the named link elimination of §4.3, and **report that you had to**.
2. **Never use positions.** `PyomoNLP` does not preserve constraint declaration order (measured: a model declaring `e1` then `e2` returned `e2` as row 0). Build the id ↔ native-name maps from `nlp.primals_names()` and `nlp.constraint_names()`, and permute by name. Record the native names in the source map. A positional assumption anywhere is a defect.
3. **Block H's declared Jacobian has exactly 9 nonzeros** (§3.2). Return a `scipy.sparse.coo_matrix` with those 9 entries and no more. Do not return 15 with zeros in six of them.
4. **Blocks implement first derivatives only.** Do not implement any Hessian method. The second-order probe (§8) calls `nlp.set_duals(λ)` then `nlp.evaluate_hessian_lag()`; whatever happens — a raised exception or returned numbers — is recorded verbatim, with the exception type and message. An exception here is an expected, honest outcome, not a failure to fix.
5. **Counters** (§3.3) count invocations of your Python value and Jacobian methods, using `spikes.p02.common.CounterSet`. Record them per `residual()` and per `jacobian()` call, and separately over the compile phase. Do not reset them in a way that hides a call.
6. **Out-of-domain states S7a and S7b** must produce `status = "invalid_trial_state"` with a message naming the variable and the value, and no numeric arrays. The typed error is raised inside the block's `evaluate_outputs`; catch it at the boundary. S6 sits exactly on the closed domain corner and must succeed.
7. **The I-form is `not_applicable` for this route**, with the reason "grey-box outputs are NLP variables; no inline composition mechanism". Write that as an explicit recorded result, not an omission.
8. **Implement the block formulas yourself** from §2.3. Do **not** import `benchmarks.p02.expected` — that module is the judge's independent expectation, and a harness that imported it could not be wrong.

### Measurements (§7)

M01 import time, M02 compile time (5 fresh subprocesses, median and min), M04 first-call times, M05 evaluation time (20 warm-up then 200 timed calls each of residual and jacobian at S1, including `set_primals`), M06 memory (RSS after numpy import, after backend import, after compile; `tracemalloc` peak during compile), M07 compile-phase callback counts, M08 structure size, M09 the source-map example for `(eq_B, lnK_B)`, `(kdef_B, T)`, `(hdef_C, l_C)` at S1 with the CSC index taken from your exported structure, never hand-typed. Set `OMP_NUM_THREADS=1` and `OPENBLAS_NUM_THREADS=1` in `run.sh`.

## Quality bar

`ruff check .` and `ruff format --check .` must pass for your files (line length 100, rules E, F, I, B, UP, N; `spikes/` is inside ruff's scope but outside mypy's and outside pytest's `testpaths`). Annotate your code anyway. Match the style of `spikes/p02/common/`.

## Stop and report rather than choosing, if

the specification leaves something genuinely open for your part; the grey-box API does not behave as §10.3 describes; a value disagrees with what §2.5 predicts and you cannot explain it; or you find yourself wanting to relax a tolerance, drop a state, or make a check pass by construction. Escalation to the coordinator is success, not failure. Finish every part that does not depend on the open point first.

## Report back

The files you wrote; the exact command you ran and its output tail; for S1 the assembled 17 × 17 Jacobian's nnz and the values of `(kdef_A,T)`, `(kdef_A,P)`, `(eq_A,lnK_A)`, `(hdef_A,l_A)`, `(energy,v_A)`; whether the `inputs=`/`outputs=` keyword form worked on the full model; the callback counts per residual and per jacobian call; what `evaluate_hessian_lag()` did, verbatim; the timing and memory numbers; and every specification item you could not implement, with the reason.
