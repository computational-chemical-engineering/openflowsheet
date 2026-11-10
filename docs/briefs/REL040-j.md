# Engineer brief: 0.4.0 cut, part 2 — the re-takes (J) and the journey at J

Status: brief, 2026-11-10. Build lane. Frank gave the go for the RC cut on 2026-11-10. **Do not spawn sub-agents
yourself.** No tag, no release, no publish, no merge into `main`, no RC job (part 3 runs it).

## Where

Branch `wp/REL040`, K3 = `<K3>` (part 1; the orchestrator fills it in when sending this brief). Main worktree for
commits: `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040`. Run tree: a **new** `git worktree add --detach
/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-k3-040 <K3>`, in which `git status --porcelain --ignored` prints
nothing before the first re-take (RP §7.1 / A-11 item 7). Record that check in the log. Outputs go outside the
repository under `~/.cache/rel040-cut/` (not tmpfs; TRS2 has reset twice).

Authority: `docs/derivations/release-procedure.md` §7.1 third bullet (A-11, R-1008), §4.5, §5.1, §12 (stops). Recipes
and expected counts: `docs/V03_RC_DECISIONS.md` lines 20–50 and 360–375 (0.3.0's K3 re-take and journey) and
`docs/RP_DECISIONS.md` lines 372–474 (S-6's REAL and IDAES re-takes). Environments:
- nlp `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.venv-nlp`, with `env -i` (HOME, PATH, LANG),
  `OMP_NUM_THREADS=1`, `PYOMO_CONFIG_DIR=<venv>/share/pyomo`, `PYTHONNOUSERSITE=1`, `PYTHONPATH=src:<m05's
  nlp-test-tools>`;
- IDAES: its pinned environment as `release_rc.py`'s step 11 uses it.

**Never install, build or `pip install -e` inside the run tree** (an egg-info broke S-6's sidecar).

**TRS2 load:** `uptime` before each heavy start. Keep the whole machine at or below ~36 busy threads, and this work at or
below 12. The three re-takes are single-threaded and may run in parallel.

## Do

1. **Re-takes at K3, each proved before it replaces anything.**
   - (a) The five in-process G10 records, by E6/K's recipe (`run_case` + `write_files`). Prove with
     `scripts/m05_retake_diff.py --digest-only --old-version <the committed records' version, read from them; expect
     0.4.0.dev0>`. Expect `PASS` ×5 with `other=0` and `environment=equal`; 0.3.0 had version leaves 4/7/4/3/4.
   - (b) M05 REAL: `scripts/m05_wo9_real.py --retake-into <dir>` (~35–55 min). Prove with `scripts/m05_retake_diff.py
     --digest-only <committed stem> <dir>/trust-region-study-real --old-platform <p>`, where p is the committed `S0`
     coupling record's `frozen.reactor.fingerprint.platform`. It must print `PASS` with `version=0 other=0
     environment=equal`.
   - (c) M01 IDAES: `benchmarks/m01/idaes_conformance.py --out <dir>/idaes-conformance.json` in the pinned IDAES env.
     Prove with `scripts/m01_idaes_retake_diff.py <committed> <dir>/idaes-conformance.json --old-platform <p>`.
2. **Commit J** in the `rel040` worktree: copy the proved files over the committed ones (only
   `benchmarks/m05/records/**` and `benchmarks/m01/idaes-conformance.json`; list the file count per record). Message
   `REL040 (J): records re-taken at K3 on the RC host (RP §7.1, R-458, R-1008)`, with every proof's summary line in the
   body. Then run `-m nlp tests/test_m05_g10_replay.py` (nlp env; 0.3.0: 5 passed) and `tests/test_m05_*retake*.py
   tests/test_m01_idaes_retake_diff.py tests/test_m07_journey_record.py`.
3. **Journey at J** (§4.5; 0.3.0's step 3 recipe):
   - run it in a new clean detached worktree at J (same `--porcelain --ignored` check), nlp env,
     `PYTHONPATH=src`, `--m05-record benchmarks/m05/records/trust-region-study-real.json`, registration budgets
     unchanged (~1 h), artifacts under `~/.cache/rel040-cut/journey/`;
   - commit the record under `benchmarks/m07/journey/<J>/` (message `REL040: the journey record at <J> (RP §4.5)`);
   - `check` must be ACCEPT;
   - `replay` at that commit, in a clean worktree, must be bitwise;
   - compare with 0.3.0's record at `2d945b5d` and list the leaves that differ. A difference beyond walls, digests,
     `commit`, R3's `m05_record` and platform strings is a stop;
   - `v0_2_gate.journey_carry(<J>, <journey commit>)` must be carried;
   - run `tests/test_m07_journey_record.py`.
4. Push `wp/REL040`. The journey-record commit is the proposed **C**. Log everything under `docs/RP_DECISIONS.md` `## 0.4.0
   cut` in its own commit after C. That commit must be outside D2.4 paths.

## Stops (RP §12; report, do not choose)

- A proof does not print `PASS`. The re-take is not committed, and the cut stops before J.
- A journey number moves beyond the classes above.
- `check` is not ACCEPT.
- The replay is not bitwise.
- Anything would need a test or tool edited.

Trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Commit named paths only. Cap ~150k context: commit, log and
stop if you near it. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`; never copy the V17 login token (R-116). Remove the two run worktrees when you finish, but keep
`~/.cache/rel040-cut/`.

## Report (at most 20 lines)

J's and C's shas in full; the proof lines; the journey's T*, J, R0–R3 and wall; the leaves that differ against
2d945b5d; check and replay; test counts; peak load; any stop.
