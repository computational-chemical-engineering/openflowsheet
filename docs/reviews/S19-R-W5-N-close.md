# S19 review R-W5-N-close: W5 batch N close (W5-K6, B_N 605d332f .. K 4178e4bc)

Reviewer (Opus), 2026-11-19, brief `<git-common-dir>/codehealth/briefs/S19-R-W5-N-close.md`. Read every diff in
scope; ran nothing. **Verdict: merge (after job 515 PASS), no fixes first.**

1. WO-N2 and WO-N3b: behaviour identity holds per step (side-effect and refusal order, exception texts, literals; bare
   `return` for a trailing `continue`; `extrapolated` merges keep key order; tables.py `errors +=` same entries at the
   same point; impact.py `out` is `self.out`). d8303d6f meets RC1 to RC3 and RC6 (field defaults in the base's order,
   before `SizingContext`). Parameters: `_Inventory.technosphere` 6 (RC7's exception is for a closing method only;
   ledger), `_searched_size` 5, others <= 4; forms.py `_Item` is a coherent parameter object. Notes: derived.py
   `_Derivation` docstring calls `earlier`/`known`/`unavailable` "frame" though they are state (RC2(b)); `section`
   now captures `run` (keeps `ctx`, `y` alive); Codehealth-Debt trailers off by 1.0 on d8303d6f and f1fed8be.
2. WO-N4 is exactly the ruling's row: `UNIT_BUILDERS` (registry_builtin.py:144) is the minimal faithful reading, since
   `BINDER` served both; METHOD_FACTORY keeps `BINDER`; legacy.json 30 factory lines; 7 `basis_provider` lines still
   name revision_binding. Out-of-gate acceptance sufficient (judge at K re-measured; job 515 full suite). Deviation to
   log: tables committed at WO-N4, while WO-N5 predicted them in K's diff (net B..K the same).
3. K meets W5-K1 (one M9 line in corpus.json, builtin-sha256.txt, the :374 substitution), nothing beyond the
   prediction; K2 and K7 met as measured. `mcp_digest` is a behaviour tier (config.toml:129-134): job 515 covers K3
   with the plain F0 tier. Run `patch_noop` once on the merge (K4). Note: from WO-N4 to WO-N6 the patch at
   test_t07_w5a_inspection.py:130 no longer covers units built through the registry factory. WO-N6: i19_scan's
   acceptance is already empty at K; give it a real test (revision_binding has no MODEL_BUILDERS; the test patches
   model_builders).
4. Tooling defaults for batches L and P: (a) w5_scope accepts `.codehealth/interface/*.toml` (repeatable `--plans`),
   only plan files added in B..HEAD (`plan_file`, w5_gate.py:245, accepts modified ones today); land on wp/S19 before
   B_L and B_P. (b) A generator-only step is gated `--behaviour-only --batch` over the step (S1, S3, S4, S6, full
   suite); the orchestrator logs the PASS as the step's acceptance; ruff and mypy on the script by the engineer, CI
   repeats. (c) The tool's rule stands; amend W5-S1's text (docs) to admit new `.py` modules in an admitted tier 1
   directory and added plan files. (d) A merge-check of K runs without `--batch` (as job 515): inside a batch, W5-S1
   and the batch-mode F0/test expectations are wrong at K, where F0 PASS 9/9 and all of L_N passing is required; K's
   diff is checked by W5-K1 and `judge`; add `w5_gate.py close --k` to make K1 mechanical; `gate_queue.py` should
   refuse `--batch` once the head contains K.
5. Merge order: no objection. wp/S19 moved one docs-only commit (490f28bc) since 05d98499: check the merge commit
   differs from 2ddc18f2 only under `docs/`; then job 515 covers it. FR-2 authorisation: confirm.

Not examined: WO-N1, WO-N3 (reviewed), w5_identity/judge code, the engineers' differential checks.
