# LINE06 F8-CYC: remove the import cycle run.replay <-> run.replay_v2 (structural, no numerics)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8cyc`, branch `wp/F8-cycle`, head `d3846b8d` (= wp/F8's
pushed, CI-green head; clean). Do not touch `.claude/worktrees/f8` or `.claude/worktrees/rel060`. Logs and scripts under
`/home/eajfpeters/.cache/line06/f8cyc/` only. Budget about 150k context. Do not push.

## The task

CI's codehealth diff on wp/F8 (run 46098069377, base main 9532829b, head d3846b8d) reports a new import cycle:
`openflowsheet.run.replay -> openflowsheet.run.replay_v2` (`src/openflowsheet/run/replay.py:248`, a function-level lazy
import so `replay()` can dispatch a manifest with `bundle_format` to `replay_v2.replay_v2`, ADR 0067 D5 step 2) and
`openflowsheet.run.replay_v2 -> openflowsheet.run.replay` (`replay_v2.py:65`, which reuses `ReplayMode`, `ReplayReport`,
`ReplayVerdict`, `Rerun`, `_as_recorded`, `_is_verdict_only`, `_verdict_drift`, `decide_mode`,
`unknown_policy_reason`). codehealth counts lazy imports as edges on purpose. The user's standing code-health rule is
0 cycles. Remove the cycle by structure alone so that the dependency runs one way.

Suggested shape (choose another only if it is clearly smaller, and log why): move the v1 pieces replay_v2 needs (the
names above, plus whatever they need) into a new module under `src/openflowsheet/run/` that imports neither `replay`
nor `replay_v2`. Both `replay.py` and `replay_v2.py` import from it, and `replay.py` re-exports every moved public name
so that every existing import path keeps working (`run.replay.ReplayReport`, `run.replay.decide_mode`,
`run.replay.REGISTERED_PLATFORMS`, used by `scripts/corpus_identity.py:767`, `application/*`, `studies/nlp/replay.py`,
`run/platform_refs.py:25`). `replay()`'s dispatch to replay_v2 then goes replay -> replay_v2 -> new module, with no
edge back. The private helpers move with their callers; keep their names. Change no behaviour, text, message or
default. Check that platform_refs.py does not create a new cycle.

## Facts and risks

- This is an intended no-op. Every digest stays exactly where it is: F0, the served-interface digest
  (`tests/test_t08_w2_surface_digest.py`, F8's pin), `list_models`, the chain digests (`tests/test_m07a_surface_chain.py`),
  the catalogue digest. Watch `__module__` and `__qualname__`: moving a class changes its `__module__`. If any digest,
  schema, pickled or serialized form, message text or replay record depends on it and moves, **STOP and report**, with
  the test name and both values. Do not re-pin anything, and do not set `__module__` by hand to hide it unless the
  report argues it is the established pattern here (grep for one first).
- `.codehealth/config.toml` holds layer rules for `run/`. The new module must sit where those rules allow.

## Acceptance (report each line)

1. `~/Code/cce-code-health/.venv/bin/codehealth diff --base 9532829b --head HEAD` (run in the worktree): no
   `new import cycle edge` lines, and no new layer violation. Report the debt line (it was 19.30 -> 54.60).
2. `python scripts/corpus_identity.py --check` (F0): PASS, all nine checks.
3. Surface suites: `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_m07a_surface_chain.py`: 0 failed.
4. Tests that touch replay: `pytest -q $(grep -rlE 'run\.replay|run import replay|replay_v2|platform_refs' tests)`:
   0 failed.
5. `ruff check` and `mypy` on the touched files: clean.
6. One commit (named paths), message naming F8 and the cycle; a DECISION entry `F8-CYC-1` in the worktree's
   `docs/F8_DECISIONS.md` saying what moved and why.

Run long test commands through `.claude/skills/line06/run.sh <name> <cmd>` (one summary line, log in
`~/.cache/line06/<name>.log`); prefix names with `f8cyc-`. Use `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`.

## Report (200-300 words)

The commit hash, what moved where, each acceptance line with its number, any STOP, anything left over.
