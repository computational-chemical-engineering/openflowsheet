# LINE06-R-TO: `scripts/release_rc.py junit-cases` (rc item F2-THREE-OS), sonnet-implementer

Do not spawn sub-agents yourself. Budget about 120k context. Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel060-to` (branch `wp/REL060-to`, from `wp/REL060`; another
engineer works on `scripts/wheel_data_check.py` in a different worktree: do not touch that file). Commit named paths
only; do not push. Report 200 to 300 words.

## Task

Add the subcommand `junit-cases` to `scripts/release_rc.py` exactly as specified in `docs/briefs/REL060-line-0.6.md`
D-3, checks TO-1 to TO-6 (about lines 95 to 140; read that section whole, it is the specification; the item's argv is
the JSON object quoted there). Reuse what exists: `push_run` (line ~108, RP §6.2's rule), `_gh_junit` (line ~237, the
artifact download; the artifact names are `junit-x86_64`, `junit-aarch64`, `junit-Windows-X64`, `junit-macOS-ARM64`,
from `.github/workflows/ci.yml` line ~199), the subcommand table in `main` (line ~509). All comparisons exact (strings,
integers). Output: `<rc>/step17/<id>/junit-cases.json` and one summary line; exit 0 iff TO-1 to TO-5 pass, 1
otherwise, 2 when the checkout is not at C or the arguments are malformed. Tests in `tests/test_rel_ci_release_rc.py`
(or a new `tests/test_rel_junit_cases.py`): the six controls (a) to (f) of TO-6 on fixture junit XML files, each
failing its named check, plus one passing case; `gh` is mocked (no network in tests), as the existing tests there do.
If the spec leaves a detail open, take the strict reading and write one line on it in the report.

## Acceptance

1. `PYTHONPATH=src /home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -m pytest -q tests/test_rel_ci_release_rc.py
   tests/test_rel_rc_items.py tests/test_rel_release_gate.py [your new test file]` passes; quote the count.
2. A live read against F2's green push run 46041020889 (commit from `gh run view 46041020889 --json headSha`) with a
   checkout at that commit is not required; instead run the subcommand's reader on the four junit artifacts of that
   run downloaded with `gh run download 46041020889 -n junit-<leg>` into a scratch directory, through a test-only or
   `--junit-dir` path if you add one, and quote: 57 matched cases per leg, all passed, same set digest on all four.
   Poll `gh` no more than needed (the API quota is shared).
