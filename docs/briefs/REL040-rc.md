# Engineer brief: 0.4.0 cut, part 3 — the RC job at C, the RC records, the lapse report

Status: brief, 2026-11-10. Build lane. Frank gave the go for the RC cut on 2026-11-10. **Do not spawn sub-agents
yourself.** No tag, no release, no publish, no merge into `main`. No `workflow_dispatch` either: the orchestrator has
dispatched it.

## Facts

- Branch `wp/REL040`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040`.
  - **C = `84c665477b512548f38a6335f51648732b1fe5bb`**: the branch head. Its D2.4 tree equals the journey record
    `b40d48d1`'s; `84c66547` adds only the part-2 log. Orchestrator DECISION: C is the head, because it carries CI's
    push run.
  - K3 = `49a0473119a7684ddf44bdf3c59528714f49337a`.
  - J = `e0a3d6b78f9d245ff8ed946ae954a9682f3e24c2`.
  - Line `0.4`, package `REL040`.
- CI at C:
  - push run `42790953372` (RP §6.2, step 1);
  - `release_rc` dispatch `42791067917` (§6.10).
  - Wait for both with one blocking loop that polls at most every 10 minutes. Do not poll faster.
- The orchestrator runs the local full gate at C. You do not.
- Authority: `docs/derivations/release-procedure.md`, §6 (steps, records, §6.9), §8.5 (the lapse report), §9.2
  steps 1–2, and §12 (stops). Runner notes: `docs/RP_DECISIONS.md` C-9…C-17. The S-6 rehearsal there (`## REL040
  prep`) has the exact inputs. Pattern: 0.3.0's `docs/v03-rc-record.md` and `docs/V03_RC_DECISIONS.md` (WO-6).
- Inputs, as at S-6:
  - `--nlp-prefix`, `--nlp-cache`: the `m05` worktree's `.venv-nlp` and `.reference-downloads/m03-ipopt`;
  - `--journey e0a3d6b78f9d245ff8ed946ae954a9682f3e24c2`;
  - `--w27-artifacts`: the `m06-w27h` worktree's `evidence/M06/W27/artifacts`;
  - `--rc` = `evidence/REL040/<C>/artifacts/rc` inside the checkout (git-ignored);
  - `--work` under `~/.cache/rel040-cut/rc/`, not tmpfs.
- `--nlp-root`: a **new** clean `git worktree add --detach … <C>`, with `git status --porcelain --ignored` empty.
  Log that check.
- **The RC checkout is its own worktree.** The orchestrator's full gate is running in the `rel040` worktree, so do not
  run the RC job there. Run it from a new `git worktree add --detach
  /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-c-040 <C>`. Use `--rc` inside that worktree, never install
  into it, and copy the records out of it into `rel040` for the commits. You may commit in `rel040` while the gate
  runs, but only under `evidence/REL040/`, `release/rc-trees/` and `docs/`. Do not run tests there until the
  orchestrator says the gate has finished.

## TRS2 load

TRS2 has reset four times under load. Run `uptime` before each heavy start, and keep the whole machine at or below
~36 busy threads. The gate (1–2 threads) and other sessions are already running. This job must use **at most 12
threads**:
- if a step spawns a pool (ensemble, G11 experiments), check its worker count first;
- if it would exceed 12 and has no knob, stop and report rather than run it.

One `local` invocation at a time. Use `--steps` subsets if that helps you keep within the load.

## Do

1. `scripts/release_rc.py local --line 0.4 …` at C, every local step of the line (2, 6–17). Run it in the background and
   wait on one completion.
2. After the dispatch completes, run `ci` (fetch the dispatch's artifacts into `<rc>/ci/`), then `items` as the runner
   requires.
3. **§9.2 step 1**:
   - `records` (`--to evidence/REL040/<C>/rc`, `--cited`, `--rc-record` = the line's `gate_set.rc_record`, `--package
     REL040`);
   - write the RC record (one row per step, plus one per item, §6.9);
   - `scripts/release_gate.py --line 0.4 --rc <C> --write-tree-record`;
   - commit the records with named paths only. Gzip any record over 1 MB, as §6.9 says.
4. **§9.2 step 2**: run `scripts/release_gate.py --line 0.4 --rc <C> --lapses` and commit
   `evidence/REL040/<C>/acceptance-lapses.txt`.
5. Log the steps, exits, first error lines and the records' SHA-256 in `docs/RP_DECISIONS.md` (`## 0.4.0 cut`).
   Push `wp/REL040`.
   - After C, no commit may touch a D2.4 path (`src/ schemas/ benchmarks/ requirements*.lock pyproject.toml
     MANIFEST.in README.md LICENSE NOTICE`).
   - Check with `git diff --name-only <C> HEAD` before each push.

## Stops (§12; report, do not choose)

- Any step or item fails. Record it as it is and do not re-run to pass.
- Step 11, 14 or 15 fails with `host_platform` ≠ `record_platform`.
- Anything would need a D2.4 change, or a test or tool edit.
- The load rule cannot be kept.

Trailers on every commit: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Cap ~150k context: commit, log and stop if you near it. Never
read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`. Never copy
the V17 login token (R-116). Remove the nlp worktree when done. Keep `~/.cache/rel040-cut/`.

## Report (at most 20 lines)

- Per step, pass or fail and its check count; the items.
- The CI push run's and the dispatch's conclusions.
- The commit shas.
- The lapse report's lines: stands, lapsed or unsupported, with a count of each, plus every lapsed line verbatim.
- The peak load.
- Any stop.
