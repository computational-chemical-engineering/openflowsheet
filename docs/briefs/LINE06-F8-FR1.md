# LINE06 F8-FR1: merge main (with X06) into wp/F8 (F8 re-chains onto X06 before its merge card)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `50b3af17` (clean; F8-CI2 on top of
`d0bc2996` = F8 + wp/F2 `80cdcfb3`). Logs under `/home/eajfpeters/.cache/line06/f8-fr1/` only; wait on log lines.
Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`. Log every choice as
`DECISION F8-FR1-<n>` in `docs/F8_DECISIONS.md` (new section at the end). Do not touch other worktrees. Budget about
150k.

## The task

F2 (`f1fdda2b`) is merged into `main` and X06 merges next, so by R-1072/R-1073 F8 is the third and decomposes onto X06's digest.
Merge wp/X06's head `7a4dcde7` (CI green on every leg, run 46075265235; merge card `ofs-x06-merge` pending; the
orchestrator merges main, docs only, on top later) into wp/F8 with a merge commit (`git merge --no-ff 7a4dcde7`),
resolving every conflict so that both sides' work stands. Merge base `80cdcfb3`
(wp/F2's head; main merged exactly that, so F2 itself brings no conflict). A trial merge against wp/X06 `7a4dcde7`
conflicted in 15 files: `benchmarks/t08/support_envelope.yaml`, `docs-site/messages/refusals.md`,
`docs/decision-register.md`, `docs/support-matrix.md`, `scripts/m07a_rc.py`, `scripts/t08_numerical_policy.py`, the two
`message_entry` fixtures under `tests/fixtures/schemas/application_results/`, `tests/test_m02_schemas.py`,
`tests/test_m04_study_job.py`, `tests/test_m05_study_record.py`, `tests/test_m07a_harvest.py`,
`tests/test_m07a_surface_chain.py`, `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`.
The same operation was done twice: F8-FR0 (DECISIONs F8-FR0-1 to -3 in `docs/F8_DECISIONS.md` on this branch) and
X06-FR0 (`git show main:docs/X06_DECISIONS.md`, section "X06-FR0", DECISIONs X06-FR0-1 to -3). Follow that pattern.

1. **Surface chain c_13** (`scripts/m07a_rc.py` `strip_f8`, the c_13 `Link`, `tests/test_m07a_surface_chain.py`,
   `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`, R-1076): today served D_13
   `3571c5c3…` with `strip_f8` -> F2's D_11 `8eee5313…`. After the merge c_13 must decompose onto X06's D_12
   `ba4b5ce59af4ac4c1e5d29f157ccd5d6308cc0a6282f0dc3434fc3b5cf88db62`: `strip_f8` of the merged served surface gives
   that exactly, `strip_x06` of that gives `8eee5313…`, `strip_f2` of that gives D_10 `f7ec3c94…`. Chain order c_11,
   c_12, c_13 kept; no renumbering. Recompute D_13 and log old -> new. Between served and `strip_f8` only
   `get_job_result` may differ (as F8-FR0-1). Followers as in F8-FR0-1 (`F8_SERVED_SHA256`, the c_13 `Link`, R-1076's
   Evidence cell, ADR 0019 Amendment 12's pointer paragraph, not its status line, `tests/f8_schema_support.py`'s
   docstring). R4-G3 and `list_models` snapshot decompositions: F8 taken out first, then X06, then F2.
2. **Catalogue digest:** regenerate (`scripts/doc_pages.py`, `msg_catalogue.py check`) and re-pin the two
   `message_entry` fixtures (`t07_schema_fixtures.py --write`, those two only); log old -> new.
3. **Harvest:** rows in merge order F2, X06, F8 at the envelope's tail. Expected `HARVEST_SIZE` = main's
   (110, 1184, 152) plus F8's own increment (F8-FR0-3: F8 on F2 is (110, 1184, 154), F2 alone (110, 1184, 151)), so
   (110, 1184, 155) if the parts add; take the value measured by `tests/test_m07a_harvest.py` and say if it differs.
   Re-emit `docs/support-matrix.md` (`t08_support_matrix.py --emit`).
4. **`scripts/t08_numerical_policy.py`, `tests/test_m05_study_record.py`:** keep every side's classifications and
   addenda; `ADDENDA` order F2, X06, F8.
5. **Decision register, prose:** keep both sides' rows and text. ADR status lines are the orchestrator's.

No change to the behaviour of any package. Any served-digest move other than c_13's recomputation, the snapshot
decompositions and the catalogue re-pin is a STOP: write the measured facts and end.

## Acceptance (judged on these alone)

Merge commit on wp/F8 (plus any follow-up commits, named paths). At the merged head: F0 PASS
(`scripts/corpus_identity.py --check`; M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42);
`scripts/w5_identity.py sets --check` PASS; `tests/test_f8_*`, `tests/test_f2_*`, `tests/test_x06_*`,
`tests/test_msg_*`, `tests/test_t07_*`, `tests/test_t08_w2_*`, `tests/test_m07a_*`, `tests/test_m02_schemas.py`,
`tests/test_m04_study_job.py`, `tests/test_m05_study_record.py`, `tests/test_k05_replay.py`,
`tests/test_v03_semantic_roles.py`, `tests/test_evidence_manifests.py`, `tests/test_s19_w5_gate.py`,
`tests/test_adr_0002_a1_integers.py` pass (counts per group; any red named with its cause); ruff,
ruff format --check, mypy src clean. Do not push. No background job of yours running when you report. Report in
200-300 words: the merge commit, conflicts and how each was resolved, the digests old -> new, HARVEST_SIZE, the
test counts.
