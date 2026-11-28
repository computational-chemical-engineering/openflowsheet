# LINE06-R-FIX: fix round on the 0.6 release machinery (sonnet-implementer)

Do not spawn sub-agents yourself. Budget about 120k context. Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel060` (branch `wp/REL060`). Commit named paths only, one
commit per fix (F-1, F-2, F-3, N-1); do not push. Report 200 to 300 words.

The review is `docs/reviews/REL060-machinery.md` (read "Fixes" and N-1). Apply exactly:

- **F-1 (must)** in `scripts/wheel_data_check.py` (`_admission` ~:567, `f2_findings` ~:654) and
  `tests/test_rel_wheel_f2.py` (control (e) ~:252): record `{"admitted": bool(report.admitted)}`; require
  `{"admitted": True}` for the base's v2. Control (e) asserts `{"admitted": True}`; a new control setting
  `refusal.v2 = {"admitted": False}` fails exactly `refusal`.
- **F-2** in `scripts/release_rc.py` (~:347) and `tests/test_rel_junit_cases.py` (`_step1` ~:52): build the tests'
  step-1 record with `release_rc.step1_checks(...)` instead of by hand; add `compared_with_step1: [legs]` to the
  `legs.junit` finding. A test asserts `compared_with_step1 == ["x86_64", "aarch64"]` on the passing fixture; the
  existing hash-mismatch test still fails exactly `legs.junit`.
- **F-3 (orchestrator DECISION: pin)**: `--case` takes an optional exact count, `<file>::<test>=<N>` (N a positive
  decimal integer; malformed -> exit 2). `legs.cases` fails on any leg whose matched count for that case differs from
  N, and records the counts. Without `=N` the behaviour is unchanged. In `release/lines/0.6.json` item `F2-THREE-OS`,
  the two `--case` values become `...::test_e_f2_3_raised_run_writes_the_v1_bundle=56` and
  `...::test_e_f2_3_run_set_is_47_g8_and_9_basis_cases=1` (measured on all four legs of run 46041020889: 56 + 1). Add
  one line to the item's `assertion` text: "exactly 56 run cases and 1 count case on each leg". Controls: a fixture
  leg set where every leg has 10 run cases fails exactly `legs.cases`; `=0`, `=x` and `=` exit 2. In
  `docs/briefs/REL060-line-0.6.md` D-3, amend TO-3 in place with one sentence naming the count and cite R-REV F-3.
- **N-1**: a control with the push run's `status` not `completed` fails exactly `legs.push_run`; control (d) asserts
  the failed set equals `{"legs.cases"}` (not membership).

Log each change as a DECISION line in `docs/REL060_DECISIONS.md` (new section "LINE06-R-FIX").

## Acceptance

1. `PYTHONPATH=src /home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -m pytest -q tests/test_rel*.py` passes; quote
   the count (332 before).
2. The loader still passes on the edited line file: `PYTHONPATH=src:scripts <venv>/bin/python -c "import
   os,subprocess,release_gate as rg; r=lambda p: open(p,'rb').read() if os.path.exists(p) else None;
   l=rg.load_line('0.6', r); print(rg.tree_problems(l, subprocess.run(['git','ls-tree','-r','--name-only','HEAD'],
   capture_output=True,text=True).stdout.split()))"` prints `[]` (run after committing).
3. The F2-THREE-OS argv parses with the new `--case` form (a test that loads the item's command from the line file and
   parses it with the subcommand's parser).
