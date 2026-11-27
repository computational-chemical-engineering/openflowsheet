# LINE06 F8-FR0: merge wp/F2 into wp/F8 (before the F8 fix round)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, head `5406f812` (clean). Logs under
`/home/eajfpeters/.cache/line06/f8-fr0/` only; wait on log lines. Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`. Log every choice as `DECISION F8-FR0-<n>` in `docs/F8_DECISIONS.md`. Do not touch the f2 or x06
worktrees. Budget about 150k.

## The task

Merge wp/F2's head `4b820b97` into wp/F8 with a merge commit (`git merge --no-ff wp/F2`), resolving every
conflict so that both packages' work stands. wp/F8 branched from wp/F2 at `df796cc2`; since then wp/F2 gained the F2
review fix round (F2-WO8: templates, catalogue, served D_11 moved `9a4b4eb3` -> `8eee5313`, F2's manifest and harvest
rows, HARVEST_SIZE (109, 1180, 151)) the j16 fixture fix (`6913c4a0`), ADR 0062 Accepted (`831d6f26`), the human review of `check_admission.md` (`8edbbaee`) and `scripts/w5_identity.py` holding `material.json` (`4b820b97`; on the merged tree `w5_identity.py sets --check` must PASS and `tests/test_s19_w5_gate.py` pass). Known conflict points (state file and
F8_DECISIONS):
1. **Surface chain c_13** (`scripts/m07a_rc.py`, `tests/test_m07a_surface_chain.py`,
   `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`, R-1076; DECISIONs F8-WO1b-*,
   l.94-132): c_13 must decompose onto F2's new `D_11` `8eee5313...` (strip F8 from the merged served surface gives
   F2's head digest exactly). Recompute c_13's `D_13` from the merged tree and log old -> new. R-1072/R-1073 rule:
   the second to merge decomposes onto the first's digest.
2. **Catalogue digest:** both branches added entries (F2's prose round, F8's `replay.yaml` + `platform_reference_used`).
   Regenerate (`scripts/doc_pages.py`, `msg_catalogue.py check`) and re-pin the two `message_entry` fixtures as WO3 /
   WO5 did; log old (F2 `3af0a794...`, F8 `bbdcfb51...`) -> new.
3. **Harvest:** keep both packages' envelope rows; `HARVEST_SIZE` taken from running `tests/test_m07a_harvest.py`
   (expected (110, 1184, 154) by sum; the run decides), `docs/support-matrix.md` re-emitted.
4. **The decision register** (R-1076 Evidence cell vs main's/F2's tail, DECISION F8-WO1b-4) and any doc conflicts:
   keep both.
5. **`tests/test_v03_semantic_roles.py`'s three reds** should go away with F2's fixes; say whether they do.

No change to the behaviour of either package. Any served-digest move other than c_13's recomputation and the
catalogue re-pin is a STOP: write the measured facts and end.

## Acceptance (judged on these alone)

Merge commit on wp/F8 (plus any follow-up commits, named paths). At the merged head: F0 PASS (M1 50/50, M2-M5 61/61,
M6 85/85, M7 52/52, M8 105/105, M9 42/42); `tests/test_f2_*`, `tests/test_f8_*`, `tests/test_k05_replay.py`,
`tests/test_x07a_*`, `tests/test_msg_*`, `tests/test_t07_*`, `tests/test_t08_w2_*`, `tests/test_m07a_*`,
`tests/test_adr_0002_a1_integers.py`, `tests/test_v03_semantic_roles.py`, `tests/test_evidence_manifests.py`,
`tests/test_t08_w2_support_envelope.py`, `tests/test_s19_w5_gate.py`, `tests/test_t08_w2_description_reviews.py` pass (report counts per group; any red is named with its cause); ruff, ruff
format --check, mypy src clean. Do not push. No background job of yours running when you report. Report in 200-300
words: the merge commit, conflicts and how each was resolved, the digests old -> new, HARVEST_SIZE, the test counts.
