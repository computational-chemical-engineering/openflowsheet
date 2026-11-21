# F3 fix round 3: the CI failures of wp/F3 6800a65f (CI run 44283813577)

Lane: build. Agent: `opus-engineer`. Worktree `.claude/worktrees/f3`, branch `wp/F3`, start at the commit that adds
this brief. Do not spawn sub-agents yourself. Read `CLAUDE.md` (repo root) first, then the tail of
`docs/F3_DECISIONS.md` (the WO7 entry). Budget about 150k tokens; at the cap commit what is complete, log where you
stopped, end. Report in at most 300 words; detail goes into `docs/F3_DECISIONS.md` as a new entry "Fix round 3".

## What CI found

The evidence (assertion lines per test, the codehealth job's output) is in
`/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/briefs/F3-ci-44283813577.txt`. Full log:
`gh run view 44283813577 --log-failed`. The 76-file battery of WO7 passed; CI runs the full suite and found:

| test | legs | what |
| --- | --- | --- |
| `test_every_description_is_reviewed_by_both_lanes` | all | expected red: Frank's human review not recorded. **Do not touch `REVIEW.json`** (an agent edit recording Frank's sign-off was refused by the permission system; it waits for Frank). |
| `test_a21_every_item_is_classified_once_and_resolves` | all | `evidence/F3/ebdff46f.../manifest.json` `checks[*]`: unmapped (6 items) |
| `test_g20_every_hit_is_allowlisted_and_every_entry_is_hit` | all | five new `@cache` hits not on the allowlist: `application/records_service.py` (1), `records/importers/legacy.py` (2), `records/model.py` (1), `records/rig...` (see the file), `records/validate.py` (1) |
| `test_m07a_a50_the_harvest_size_is_the_quoted_one` | all | `(99, 1134, 147) != (98, 1129, 146)` |
| `test_no_broad_except` | all | a re-raising broad handler outside `src/openflowsheet/application/` |
| `test_t07_q26_no_external_state` and the container-shape test | all | `Finding(operation='validate_record', path=('reactions', '*', 'stoichiometry'), kind='map')` not in `ALLOWED_BY_PATH` |
| `test_e_f3_8_two_processes_register_200_overlapping_records` | x86, default-install (not arm) | `sqlite3.OperationalError: database is locked` in a worker's `store.register` |

Codehealth job (informational, `continue-on-error`): its 26 `repo-layers` "new architecture violation" lines are an
artefact: `codehealth diff` ratchets the head against the **base's** config (cce-code-health
`architecture.compare_refs`), and main's config has no `records` entries; at the head, `codehealth arch --depth 4`
reports 0 violations, 0 cycles. No action on those. Real: `FAIL src/openflowsheet/application/local.py: new file
smell(s) duplication (nloc 411)` and "debt over touched files rose 51.60 -> 62.70".

## The work (one commit per item, message naming F3 fix3)

1. **A21**: map the manifest's checks the way the test requires (read the test and an accepted manifest, e.g.
   `evidence/F1/a423093f.../manifest.json`). Mechanical.
2. **A50 harvest size**: find where the size is quoted, establish which F3 test rows add the 1 / 5 / 1, and update the
   quote with the reason in the same commit (as WITNF did with `HARVEST_SIZE`). If the new rows are not F3's, stop
   and report.
3. **e_f3_8 (a real defect until shown otherwise)**: two processes registering overlapping records must both succeed
   (ADR 0061's store contract; read the test). Find why SQLite reports locked on x86 CI and not locally or on arm
   (busy timeout, transaction mode, a read transaction upgraded to write). Fix in the store; prove it by running the
   test 50 times in a loop and under CPU load (`stress`-like: run it beside `pytest -n 8` of another file); report
   both counts.
4. **`local.py` duplication smell**: remove the new duplicate (find it with `codehealth scan --json <out>` on the file
   and `git diff main -- src/openflowsheet/application/local.py`); behaviour unchanged.
5. **Choices for the design lane (make each as one isolated, revertible commit; log each as `DECISION F3-3-n:
   <question> -> <choice>. Alternative: <x>. Reversible by: <how>`; they are ruled in one round after this run)**:
   - G20: each of the five `@cache` hits either goes on the allowlist with the allowlist's own justification form
     (what it caches, keyed on what, why it cannot hold external state) or is removed. A cache on non-canonical or
     mutable inputs is removed, not listed.
   - Q26 / container shapes: `validate_record`'s `reactions[*].stoichiometry` is a map (ADR 0061's reaction form). Add
     it to `ALLOWED_BY_PATH` with the ADR clause that makes it a model input, or change the schema if ADR 0061 allows
     another form. Do not change ADR 0061.
   - `test_no_broad_except`: narrow the handler to the exceptions it must clean up after; if it must stay broad and
     re-raising outside `application/`, the choice and its reason go to the ruling round (do not edit the test's rule
     on your own).
6. **Codehealth**: report the touched-files debt at the end against 62.70 (`codehealth diff --base main --head HEAD`);
   reduce it where an item above touches the code anyway; no separate refactor.
7. **The full suite once, at the end**: `TMPDIR=$HOME/.cache/openflowsheet/tmp-f3 PYTHONPATH=src
   /home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -m pytest -q -p no:cacheprovider -n 8 --timeout=900
   tests/ > <scratch>/full.log 2>&1` in the background (one summary line; read the log only on failure, by grep).
   Pass: the only failure is `test_every_description_is_reviewed_by_both_lanes`. Never stop or kill a pytest process
   you did not start (gate jobs of another lane run on this machine).
8. **Manifest**: move it to the new head commit (`evidence/F3/<new sha>/manifest.json`, the old one removed in the
   same commit as WO7 did), status `implemented`, commands as run; push `wp/F3` (`git -c
   credential.helper='!gh auth git-credential' push`); report the CI run ID; do not wait for it.

## Report

Per item: commit SHA, what changed, the evidence number (loop counts for 3; the full-suite line for 7); the DECISIONs
of item 5; anything not done and why.
