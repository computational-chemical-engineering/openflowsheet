# LINE06 X06-FR0: merge wp/F2 into wp/X06 (X06 re-chains onto F2 before its merge card)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06`, head `73b3a83d` (clean; CI green on all
legs, run 46044426797). Logs under `/home/eajfpeters/.cache/line06/x06-fr0/` only; wait on log lines. Tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`. Log every choice as `DECISION X06-FR0-<n>`
in `docs/X06_DECISIONS.md` (new section at the end). Do not touch the f2 or f8 worktrees. Budget about 150k.

## The task

F2 merges into `main` first (card `ofs-f2-merge`, pending), so by R-1072/R-1073 X06 is the second and decomposes onto
F2's digest. Merge wp/F2's head `80cdcfb3` into wp/X06 with a merge commit (`git merge --no-ff 80cdcfb3`), resolving
every conflict so that both packages' work stands. Merge base `d00f659a`. A trial merge conflicts in 17 files:
`benchmarks/t08/support_envelope.yaml`, `docs-site/messages/refusals.md`, `docs/interfaces-frozen.md`,
`docs/support-matrix.md`, `scripts/m07a_rc.py`, `scripts/t08_numerical_policy.py`,
`src/openflowsheet/application/jobs/runner.py`, `src/openflowsheet/messages/catalogue/refusals.yaml`, the two
`message_entry` fixtures under `tests/fixtures/schemas/application_results/`, `tests/test_m02_schemas.py`,
`tests/test_m04_study_job.py`, `tests/test_m05_study_record.py`, `tests/test_m07a_harvest.py`,
`tests/test_m07a_surface_chain.py`, `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`.
The same operation was done for F8 (brief `docs/briefs/LINE06-F8-FR0.md`, DECISIONs F8-FR0-* in `wp/F8:docs/F8_DECISIONS.md`,
read with `git show wp/F8:<path>`): follow that pattern.

1. **Surface chain c_12** (`scripts/m07a_rc.py` `strip_x06`, `tests/test_m07a_surface_chain.py`,
   `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`, R-1073): today
   `X06_SERVED_SHA256` = D_12 `7792576e...` with `without_x06` -> F3's D_10 `f7ec3c94...`. After the merge c_12 must
   decompose onto F2's D_11 `8eee5313...` (strip_x06 of the merged served surface gives F2's head digest exactly;
   strip_f2 of that gives `f7ec3c94...`). Chain order c_11 (F2) then c_12 (X06) is kept; no renumbering. Recompute
   D_12 from the merged tree and log old -> new. Same for the R4-G3 / `list_models` snapshot decompositions
   (`without_x06` lands on F2's values).
2. **Catalogue digest:** both branches added refusals. Regenerate (`scripts/doc_pages.py`, `msg_catalogue.py check`) and
   re-pin the two `message_entry` fixtures; log old (F2's and X06's) -> new.
3. **Harvest:** keep both packages' envelope rows; `HARVEST_SIZE` is (109, 1180, 151) on F2 and (109, 1180, 148) on
   X06; take the merged value from running `tests/test_m07a_harvest.py`; re-emit `docs/support-matrix.md`.
4. **`scripts/t08_numerical_policy.py`:** X06 added `benchmarks/x06/numerical_policy_external.yaml` (X06-CI1);
   keep F2's classifications and X06's addendum both.
5. **`jobs/runner.py`:** keep both behaviours; name in the report what each side changed there.
6. **Docs** (`docs/interfaces-frozen.md`, the register, anything else): keep both. The ADR 0019 amendment status
   lines are the orchestrator's; leave their wording as each side has it.

No change to the behaviour of either package. Any served-digest move other than c_12's recomputation, the snapshot
decompositions and the catalogue re-pin is a STOP: write the measured facts and end.

## Acceptance (judged on these alone)

Merge commit on wp/X06 (plus any follow-up commits, named paths). At the merged head: F0 PASS
(`scripts/corpus_identity.py --check`; M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42);
`scripts/w5_identity.py sets --check` PASS; `tests/test_f2_*`, `tests/test_x06_*`, `tests/test_msg_*`,
`tests/test_t07_*`, `tests/test_t08_w2_*`, `tests/test_m07a_*`, `tests/test_m02_schemas.py`,
`tests/test_m04_study_job.py`, `tests/test_m05_study_record.py`, `tests/test_k05_replay.py`,
`tests/test_v03_semantic_roles.py`, `tests/test_evidence_manifests.py`, `tests/test_s19_w5_gate.py`,
`tests/test_adr_0002_a1_integers.py` pass (report counts per group; any red named with its cause); ruff,
ruff format --check, mypy src clean. Do not push. No background job of yours running when you report. Report in
200-300 words: the merge commit, conflicts and how each was resolved, the digests old -> new, HARVEST_SIZE, the
test counts.
