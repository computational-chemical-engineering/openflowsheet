# LINE06 F8-WO1b: the two stopped WO1 items, registered as surface link c_13 (R-1076)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `1b7e1b51` (clean; F8-WO1 done except
its STOPs 8 and 9). Logs and scripts under `/home/eajfpeters/.cache/line06/f8-wo1b/` only; wait on log lines, not
`kill -0`. For tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`; F0 with
`--log /home/eajfpeters/.cache/line06/f8-wo1b/f0-detail.log`. Log every choice as `DECISION F8-WO1b-<n>` in
`docs/F8_DECISIONS.md`. Budget about 150k: at the cap, commit what is complete, write where you stopped, and end. A
reviewer reads `.claude/worktrees/f2` meanwhile; do not touch that worktree.

## The task

Build what F8-WO1 stopped on, now that the move is registered: **R-1076** (`docs/decision-register.md` on `main`,
the last entry) makes F8's surface moves chain link **c_13**, decomposing onto F2's c_11 on wp/F8 (wp/F8 branches
from wp/F2), with `strip_f8` in `scripts/m07a_rc.py` and `without_f8` for the R4-G3 snapshot decompositions. Follow
the c_11 (F2, `strip_f2`, R-1072; carried onto wp/F2 by DECISION WO3-1 in `docs/F2_DECISIONS.md`) and c_12 (X06,
`strip_x06`, R-1073, on wp/X06: read it with `git show wp/X06:<path>`, do not check it out) pattern exactly.

1. **STOP F8-WO1-8** (`docs/F8_DECISIONS.md` line ~59): wire `replay-report.schema.json` per ADR 0067 D5
   (Amendment 12): `forced_replay` in `mode` (reserved; the Python refusal `construct_unavailable(forced_replay, TX)`
   already exists, WO1-6), `registry_comparison` and `data_availability` by `$ref` to
   `bundle-v2.schema.json#/$defs/...` (already defined and tested).
2. **STOP F8-WO1-9** (line ~67): the D3 artifact kinds in `job.schema.json` (`artifact_ref.kind`), `jobs/model.py`'s
   `ArtifactKind` and `ARTIFACT_FILE_NAMES` (D3 names `data-lock.json`, `registry-snapshot.json`,
   `records-index.json`, `run-evidence.json`; `record` and `decision_record` per instance, `None`). `exchange_record`:
   D10 gives no file name; log the choice (default: `None`, as per-instance).
3. **Register the move:** `strip_f8` (chain) and `without_f8` (snapshots), the `F8_SERVED_SHA256` constant and link
   c_13's entry, the R4-G3 snapshot re-pins with their `without_f8` decompositions back to the pre-F8 values (old ->
   new logged for each); R-1076's evidence row filled with the measured numbers on wp/F8 (edit only that entry's
   Evidence cell in `docs/decision-register.md` on wp/F8; the orchestrator mirrors it to `main`).

## Acceptance (judged on these alone)

`tests/test_m07a_surface_chain.py`, `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`
and the other surface suites (`tests/test_t07_*`, `tests/test_t08_w2_*`) pass, except the known reds named in
F8-WO1-10 (`tests/test_v03_semantic_roles.py`, F2's, with the reviewer); `without_f8(served)` reproduces F2's
`9a4b4eb3…` digest and each pre-F8 R4-G3 snapshot exactly; `tests/test_f8_manifest_v2.py`, `tests/test_k05_replay.py`
and the job-model tests pass; F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42); ruff,
ruff format --check, mypy src clean. A digest move that `without_f8` does not return to its pre-F8 value is a STOP.

Commit named paths only, never `git add -A`; do not push. Make sure no background job of yours runs before you
report. Report in 200-300 words: commits, test counts per file, F0 line, each re-pin (old -> new), DECISIONs.
