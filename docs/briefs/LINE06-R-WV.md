# LINE06-R-WV: `scripts/wheel_data_check.py --f2` (rc item WHEEL-F2), opus-engineer

Do not spawn sub-agents yourself. Budget about 150k context; at the cap, commit what is complete, write where you
stopped in `docs/REL060_DECISIONS.md` (create it, append-only, "the user" not first names) and end. Rules:
`docs/LINE06_RULES.md`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel060` (branch `wp/REL060`).
Commit named paths only; do not push. Report 200 to 300 words.

## Task

Add `--f2` to `scripts/wheel_data_check.py` exactly as specified in `docs/briefs/REL060-line-0.6.md` D-5, assertions
WV-1 to WV-6 (lines about 180 to 245; read that section whole, it is the specification), with the five controls (a) to
(e) of WV-6 as tests in a new `tests/test_rel_wheel_f2.py`. Follow the established `--f1-f3` pattern (commits
1dee789c, 1452d786; `tests/test_rel_wheel_f1_f3.py`): probe mode in a fresh venv with `-I`, `--in-checkout` for the
tests, one summary line `wheel data check (F2): PASS|FAIL`, exit 0 / 1 / 2 as WV-6 states. No floating point is
compared: digests and ids as strings. The independent expectation of WV-4 is F0's registered M3 r0 (the corpus
registry), never a value computed by the code under test. If the spec is ambiguous or a stated fact is false in the
tree (a name, a path, a registered value), log it as a DECISION in `docs/REL060_DECISIONS.md` with the alternative,
choose the reading that keeps the check strict, and carry on; stop only if a choice would change numerics or a frozen
interface.

## Acceptance

1. `PYTHONPATH=src <main>/.venv/bin/python -m pytest -q tests/test_rel_wheel_f2.py tests/test_rel_wheel_f1_f3.py
   tests/test_rel_rc_items.py tests/test_rel_release_gate.py` passes, each of the five controls failing its named check.
2. A real run `PYTHONPATH=src <main>/.venv/bin/python scripts/wheel_data_check.py --commit $(git rev-parse HEAD) --f2`
   on a clean checkout prints `wheel data check (F2): PASS` and exits 0 (quote the line and the five digests). Run it
   with its log in a file; read the log only on failure.
3. `--f1-f3` unchanged in behaviour (its tests pass unmodified).
