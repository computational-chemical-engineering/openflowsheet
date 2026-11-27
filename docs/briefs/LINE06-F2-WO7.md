# LINE06 F2-WO7: F2 close-out (ADR 0062 work order 7)

Build lane, `sonnet-implementer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2`, head `2d19b5f8` (clean; WO1 to WO6c done
and judged). Logs and scripts under `/home/eajfpeters/.cache/line06/f2-wo7/` only. For tests in this worktree:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`. Log every choice in `docs/F2_DECISIONS.md`
as `DECISION WO7-<n>`. Budget about 150k: at the cap, commit what is complete, write where you stopped, and end.
Another engineer works in `.claude/worktrees/f8`: do not touch it.

## The task (four items, one commit each)

1. **Catalogue prose (DECISION WO4-16, `docs/F2_DECISIONS.md` line ~329).** The 18 minimal entries WO4 added (17
   refusals in `src/openflowsheet/messages/catalogue/refusals.yaml`, `species_basis_not_monotone` in `notices.yaml`)
   get full prose in the style of a complete existing entry in the same file (pick one with `complete: true` and copy
   its field set): title, summary, cause, remedy, params as the emitting code passes them (read each emit site in
   `src/openflowsheet/material/` and `revision_v2/`; ADR 0062 section "Exit tests" E-F2-9's code table states the
   meaning of each code). Set `complete: true` only when every field the complete style has is filled. Reconcile
   `molar_mass_inconsistent`'s params with both emitters (F3: `reaction`; F2 basis notice: `definition, substream,
   species`) as optional params, not by dropping either. Then `python scripts/doc_pages.py` (re-emit
   `docs-site/messages/{refusals,notices}.md`) and its `--check` if it has one. The catalogue digest moves: re-pin
   the two `message_entry` fixtures of `tests/test_t07_w5e_application_results.py` exactly as WO4 did (see WO4-16)
   and log old -> new.
2. **Optimization on a v2 revision (WO6b "Not done", line ~609).** A test in `tests/test_f2_amendment9.py`: take the
   revision one of the existing NLP tests optimizes (`tests/test_opt_job_nlp.py` or `tests/test_opt_cost_lca_nlp.py`;
   `optimize_revision` is `src/openflowsheet/studies/nlp/revision.py:174`), raise it to v2 with
   `revision_v2.raise_v1`, optimize both, assert the results' identity fields and the optimum values are equal (the same
   comparison the existing test makes for v1). If the nlp extra is absent, skip with the existing tests' marker. **If the
   v2 run differs or errors, do not fix `src/`: commit the test marked `xfail(strict=True)` with the observed failure,
   log it, and report it as a finding.**
3. **Evidence manifest** `evidence/F2/<head commit>/manifest.json`, `status: tested`, in the shape of
   `evidence/F3/6c82b535.../manifest.json` (copy its field set). One row per exit E-F2-1 to E-F2-10 naming the test
   file(s) and test ids that carry it (find them via `docs/F2_DECISIONS.md` gate entries and `grep -n "E-F2-" tests/`),
   with the command you ran and its real pass count. Every command in it must be one you ran at the head the manifest
   names; no angle-bracket values. `reviewed` is never set (the design lane sets it).
4. **Gate (by risk; CLAUDE.md):** run every test file the four commits touch plus `tests/test_msg_*.py`,
   `tests/test_f2_*.py`, `tests/test_f1_draft_admission.py`, `tests/test_t07_w5e_application_results.py`, then F0:
   `python scripts/corpus_identity.py --check --log ~/.cache/line06/f2-wo7/f0-detail.log` (must print `F0 PASS` with
   M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42). ruff, ruff format --check, `mypy src` clean.

## Not in scope

- `check_admission.md` (DECISION WO6b-6): it moves the served digest (chain link c_11) and voids reviews; the
  orchestrator handles it with the F2 reviewer pass. **Any change to a served digest is a STOP: commit nothing
  further and report.** Run `python scripts/corpus_identity.py --check` and the served-digest tests to confirm none
  moved.
- No change to `src/` beyond the catalogue YAML (and only if item 1 needs a param name aligned, log it).

## Acceptance (judged on these alone)

Items 1 to 4 committed; the touched tests and the listed suites pass (or item 2's strict xfail with its finding); F0
PASS; no served digest moved; manifest present with real commands and counts. Commit named paths only, never
`git add -A`; do not push. Make sure no background job of yours runs before you report. Report in 200-300 words:
commits, test counts per file, F0 line, the catalogue digest re-pin, item 2's outcome, anything left over.
