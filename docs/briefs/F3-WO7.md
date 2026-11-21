# F3-WO7: close-out of F3 (component data, ADR 0061)

Lane: build. Agent: `sonnet-implementer`. Worktree `.claude/worktrees/f3`, branch `wp/F3`, start at the commit after
`c1cee7e1` that adds this brief. Do not spawn sub-agents yourself. Read `CLAUDE.md` (repo root) first; the scientific
content is settled, nothing here decides numerics. Report in at most 250 words; detail goes into `docs/F3_DECISIONS.md`
as a new entry "WO7 (close-out)", in the form of the entries above it.

## Facts already established (do not re-derive)

- ADR 0061 is Accepted (R-1050). F3 review 2 (`docs/reviews/F3-review-2.md`, 68ca5b98) and its fix round 2
  (afde8883) are done. The design-lane review of the five MCP descriptions is recorded in `REVIEW.json` at c1cee7e1;
  Frank's human review is pending (requested through the Decision Desk). Do not touch `REVIEW.json`.
- The served MCP digest D_10 is now `f7ec3c94233d30506ec2082a13c4e54d57bd540e43e97fdf877b1e3c75fed467`
  (`tests/test_t08_w2_surface_digest.py:155`); `248c2e74…` is the digest at F3-WO5b, superseded at C6 and C11.
- `tests/test_t07_w6c_descriptions.py::test_g15_one_description_per_mcp_operation_and_no_other` fails today:
  `assert len(MCP_OPERATIONS) == 21` at line 48, the count is 26. Review 2's C9 fixed the twin assertion in
  `tests/test_t08_w2_description_reviews.py:35` but missed this one; the 62-file battery does not contain the file.
- `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes` is the one expected
  red: it now reports the five human reviews open (5, not 10). It stays red until Frank's review is recorded.

## Commits (one each, message names F3 WO7, attribution lines as in the recent commits)

1. **Test count.** `tests/test_t07_w6c_descriptions.py:47-48`: 26, and the comment gains "ADR 0061 D13 (F3): five
   more" in the style of the existing comment. Then grep `tests/` for other hard-coded counts of operations, MCP tools,
   descriptions or registry descriptors that F3's additions changed (`grep -n "== 19\|== 21\|== 42" tests/*.py`, and
   read each hit; fix only those that count F3's additions, with the same kind of comment). List every hit and the
   verdict in the log entry.
2. **Register R-1051** (`docs/decision-register.md:20009-20030` or so): the heading and the **Decision** paragraph name
   `f7ec3c94…` instead of `248c2e74…`. Keep the Evidence row as it is (it already records both digests and the history).
3. **ADR 0019 Amendment 8, the `reserved_namespace` sentence** (`docs/adr/0019-application-contract-v1.md:275-276`):
   rewrite it to say what R-1056 decided (read `docs/decision-register.md` from line 20132, the R-1056 entry, and
   review 2's C3): a record naming a `legacy.` source, or carrying a `legacy` member, whose SHA is not in the committed
   legacy index is refused `reserved_namespace(legacy)`, in the code's record variant (R-1056). One sentence, no other
   change to the ADR.
4. **Descriptor status.** `scripts/registry_builtin.py:513-514`: `RECORDS_STATUS = "tested"`, its comment saying
   F3's close-out raised it (ADR 0060 D10: status is an evidence field, excluded from every hash). Regenerate with the
   script's write mode (read its docstring, lines 1-20), then `--check`. Acceptance: only `status` values change in
   the generated tables; the two digest files beside them are byte-identical (`git diff --stat` shows them unchanged).
   If a digest changes, stop: revert this commit and report it.
   DECISION (orchestrator): `tested`, not `released` (F1's legacy rows) and not left at `implemented`. Reversible by
   reverting this commit.
5. **Checks, then the manifest.** At the head of commit 4, run and record (one summary line each, logs under the
   scratch directory the shell gives you, never in the repo):
   - the battery: the 62 files of `$(git rev-parse --git-common-dir)/codehealth/briefs/F3-battery.txt` plus
     `tests/test_f3_*.py`, `tests/test_m04_study_job.py`, `tests/test_m07a_surface_chain.py`,
     `tests/test_t08_w2_description_reviews.py`, `tests/test_t07_w6c_descriptions.py`, and every other test file that
     matches `grep -ln "MCP_OPERATIONS\|len(OPERATIONS)\|REVIEW.json\|records.json\|list_tools" tests/*.py`; serial,
     `PYTHONPATH=src`, the repo-root `.venv` (`/home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -m pytest -q
     -p no:cacheprovider`). Pass: exactly one failure, `test_every_description_is_reviewed_by_both_lanes`, reporting
     the five human reviews.
   - `scripts/registry_builtin.py --check`, `scripts/records_legacy_index.py --check`, `scripts/corpus_identity.py
     --check` (F0), `ruff check .`, `ruff format --check .`, `mypy`.
   Then write `evidence/F3/<commit 4 full SHA>/manifest.json` in the form of
   `evidence/F1/a423093f2f67b83cb6f4a2d5314d27a6b0c1cbf5/manifest.json` (same keys; `work_package` F3; inputs:
   ADR 0061 with its sha256 and acceptance R-1050, the environment lock hash computed as F1's was). `status`:
   `implemented`. `commands`: only what you ran, with real exit codes and summary numbers. `review`: the WO1 review,
   ruling round 1 (`docs/reviews/F3-rulings-1.md`), review 2 (68ca5b98) and fix round 2 (afde8883), design-lane review
   of the five descriptions recorded (c1cee7e1); human review `pending`. Never `reviewed` or `tested` as the package
   status. `limitations`: Frank's human review of the five descriptions pending (and the one red test it causes);
   card ofs-f3-qf1-rational-coefficients open (rational coefficients through `validate_record`, default A: with ADR
   0062); the `molar_mass_inconsistent` signature differs between ADR 0061 and ADR 0062 (open for the design lane);
   no CI result yet (the orchestrator sets `tested` on CI green). No angle-bracket placeholders anywhere.
   Commit the manifest and the log entry together.
6. **Push.** `git push -u origin wp/F3`. Find the CI run it starts (`gh run list --branch wp/F3 --limit 3`) and report
   its ID. Do not wait for it; end.

## Acceptance (report each)

The commits 1-5 and their SHAs; the grep hits of step 1 with verdicts; the battery line (passed, failed = the one
expected red, skipped); the six check lines; the digest files unchanged by step 4; the pushed head and the CI run ID.
Anything you could not do: say so, with the failing line.
