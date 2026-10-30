# V03 brief 7: WO-6 — the RC job at C, steps 1–17, the RC record, the tree record, S13 (build lane)

Branch `wp/V03-rc` (worktree `.claude/worktrees/v03rc`); `main` = K3 `295a2e65` (0.3.0, `v0.3-envelope-1`). WO-5's journey
record and G10 re-take are on the branch (`docs/V03_RC_DECISIONS.md` has the log and handoff). Specification
`docs/derivations/V03-release-spec.md` §4 (steps 1–18, 17a–17e, CI at C), §7 (A17, A19–A24, A27), §10 WO-6 (incl. review
F-V3: the producer of `step17/rc-step17c.json` and the call of `mr12_extras_v03`), §10.1 stops. Pattern: 0.2.0's
`docs/v02-rc-record.md` (records under `evidence/M07/ce99365…/rc/`, `rc/records.json`, tools under `…/tools/`), the alpha
spec §8.2 steps as M07 §8 reads them, `scripts/m07a_rc.py`, `scripts/t08_rc.py`, CI's `rc-steps` and `rc-coolprop` jobs.

**D2.4 rule:** from K3 to dispatch no commit touches `src/`, `benchmarks/`, `schemas/`, `requirements*.lock`,
`pyproject.toml`. Anything in the RC that would need such a change is a stop (report; a re-cut is the design lane's call).

1. **Cut C** (one commit or a few, outside D2.4): the step-17c record producer and `mr12_extras_v03`'s wiring (F-V3; a missing
   record fails the measure), anything else WO-6 needs before the steps run. Run the tests you touch. **Stop and report C's
   sha**: the orchestrator pushes `wp/V03-rc` and dispatches CI at C (`rc-steps`, `rc-coolprop`, distribution) — tell it the
   exact `workflow_dispatch` inputs (read `ci.yml`). Continue the local steps while CI runs.
2. **Local steps at C** (a clean `git worktree` or checkout of C, private temp dirs): 1–17 as §4's table; 17a A48
   (`a48_release_check()` → pass, 0); 17b with `requirements-coolprop.lock` after the main lock, `--no-deps
   --require-hashes`, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, 0 skipped (CI's `rc-coolprop` job is the step's record; a local run
   is a cross-check); 17c MR-12 v03 `new_since_v0_2_0 == ["coolprop", "lca"]`; 17d A24/A25 in the `lca` env
   (`scripts/build-lca-env.sh`), A33–A36 in the audited `nlp` env; 17e wheel via `scripts/t08_dist.py`, inspected (A17),
   fresh-venv install (A19). Step 15: `v0_3_gate.py --rc C --carry-journey K3`, then `check` and `replay` at C.
3. **Records**: commit them under `evidence/S13/<C>/rc/` with `rc/records.json` (sha256, size, how kept; >1 MB gzipped), the
   tools under `…/tools/`; `docs/v03-rc-record.md` in `v02-rc-record.md`'s form (reports, judges nothing; closed vocabulary);
   `release/rc-trees/<C>.json` (R-151); `evidence/S13/<C>/manifest.json` (status `tested` only if every assertion it owns
   holds; never `reviewed`; it may cite S13a). Step 18 is not run (it needs the ledger, WO-8).
4. A failing step stays failed and is recorded as such. Diagnose, log, and stop if the fix needs a D2.4 change or changes a
   check; an outside-D2.4 tooling fix is allowed (DECISION line) but means a new C — report before re-running.

Rules: DECISION lines and the run log in `docs/V03_RC_DECISIONS.md`; pytest with private `TMPDIR` / `--basetemp` under
`/home/frankp/.cache/v03rc-tmp` (TMPDIR only for `s11_identity.py`; no shared `--basetemp` across its shards); never `/tmp`
directly; run long jobs in the background, one wait each, logs to files, read only on failure; named-path staging; commit
messages name V03; do not push; no subagents; no personal identifiers to external services; never read, copy or touch
`~/.config/procsim/v17-token` (if a step needs the V17 login, stop and report — do not look for the token). ~150k context
cap: commit, ≤40-line handoff at the end of `docs/V03_RC_DECISIONS.md`, end. Report ≤15 lines.
