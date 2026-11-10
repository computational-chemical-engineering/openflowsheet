# REL040 handoff: TRS2 → SMM-TR09 (2026-11-10)

TRS2 is rebooting. Frank continues from SMM-TR09 (session OpenFlowsheet-TR09). That session finishes the 0.4.0 release
from here. This file is the position. The history is in `docs/RP_DECISIONS.md` `## 0.4.0 cut` and the commit log of
`wp/REL040`.

## Where we are

- Branch `wp/REL040` (pushed). C = `84c665477b512548f38a6335f51648732b1fe5bb`, K3 = `49a04731`, J = `e0a3d6b7`.
- Done (RP §9.2):
  - Step 1: the RC records (124), RC record `docs/REL040-rc-record.md`, `rc/records.json`, tree record. Every step and
    item passed.
  - CI: push run 42790953372 green on both architectures; dispatch 42791067917 passed all 13 RC jobs.
  - Local full gate at C: PASS, 16678 passed.
  - Step 2: lapse report `evidence/REL040/<C>/acceptance-lapses.txt`. `V17 carry` and `V14 (b)` lapsed; the other
    five rows stand.
  - Step 3: verdicts `docs/reviews/REL040-verdicts.md` (3e6f0d80): 13 PASS, V13 BLOCKED (e), V17 BLOCKED (a), V14 FAIL
    (b), X31 FAIL (c) (its row stands). Ledger `docs/requirements.yaml` (ad7da7e2). Notes `CHANGELOG.md` `## v0.4.0`
    (f167d4ca). RP amendment A-12 (08e82e7d, R-1009).
- **Frank's answers** (decision board https://claude.ai/artifact/WBLrhuGuG9zosGy46Z1b2A, collection `answers`). These
  are his words; record them verbatim:
  - `rel040-v17-carry`: choice `reuse` = "Reuse 0.2.0's agent run (Recommended)", 2026-11-10T13:29:14Z.
  - `rel040-v14b`: choice `accept` = "Accept (Recommended)", 2026-11-10T13:30:17Z.
  - In chat on TRS2, about 13:35Z: "okay start the release procedure. After this I continue from SMM-TR09."

## Next actions, in order

1. **Acceptance rows** (RP §8.4) in `release/acceptances.md`:
   - Replace the `V17 carry` decision row and the `V14 (b)` clause row. Each new row carries Frank's words verbatim
     (the 0.3.0 rows show the cell form), the date 2026-11-10, the scope unchanged, the fingerprint evaluated at C, and
     `Accepted at` = C.
   - Move each replaced row, unedited, to the history list with "lapsed at C = 84c66547, 2026-11-10".
   - The V17 row's text names all eight links: R-192, R-234, R-295, R-934, R-950, R-960, R-1000 and R-1010.
   - Then run `release_gate.py --line 0.4 --rc <C> --lapses`; it should print 7 × stands.
2. **Re-judgement** (fresh `verdict` agent, as V03's WO-8 `f3f0ebd6` did):
   - V13 (e) and V17 (a), on the new `V17 carry` row → expect PASS;
   - V14 stays FAIL (b), now releasable.
   - Then update the ledger rows for V13 and V17 (`tests/test_rel040_ledger.py` pins them; update it with them).
3. **Notes:** fill the `<!-- acceptances: filled after Frank's answers -->` placeholder in `CHANGELOG.md` `## v0.4.0`.
   The `X31 (c)` acceptance line already exists exactly once (RP.S10). Do not add it again.
4. **H1** (RP §9.2 step 4): the release manifest `evidence/REL040/<C>/manifest.json`, generated `tested` at a clean
   commit G (`scripts/release_evidence_manifest.py`; 0.3.0 pattern in `docs/V03_RC_DECISIONS.md`), committed alone.
5. **H2:** mark Accepted the ADRs whose condition is the manifest (RP §9.1, §6.8).
6. **Step 18 at H2:** `PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line 0.4 --rc <C>`. It must exit 0
   with the last line exactly `v0.4.0 tag may be proposed: YES`. Log it to
   `evidence/REL040/<C>/artifacts/step18-H2.log`.
7. **H3:** the build log `docs/REL040_RC_DECISIONS.md` (or `## 0.4.0 cut` in RP_DECISIONS, as the line file names it):
   H2, the command, the exit, the log's SHA-256, the last line, the RP.S08 summary.
8. **Merge** `wp/REL040` into `main` with a merge commit, after CI at the head is green on both architectures. On main
   after the merge, run `ruff check`, `ruff format --check`, `scripts/corpus_identity.py --check` (F0) and the targeted
   tests, then push. Never change a D2.4 path after C: check `git diff --name-only <C> HEAD` against `src/ schemas/
   benchmarks/ requirements*.lock pyproject.toml MANIFEST.in README.md LICENSE NOTICE`.
9. **Release workflow** (GitHub only; nothing local):
   - Dry run first: `gh workflow run release.yml --ref main -f version=0.4.0 -f rc=<C full> -f dry_run=true`. Pass
     `rc` explicitly, because the default `67c66d98…` is stale.
   - Then confirm with Frank in the TR09 session before the real dispatch (`dry_run=false`). That dispatch tags
     `v0.4.0`.
   - The PyPI upload waits for Frank's approval in the GitHub environment `pypi`. That click is his.

## Stops (RP §12): report to Frank, do not choose

- The step-18 last line is not YES.
- A check needs a D2.4 change, or a test or tool edit beyond the ledger test.
- The manifest generator needs a git-ignored artifact that exists only on TRS2. The RC artifacts are under TRS2's
  `.claude/worktrees/rc-c-040/evidence/REL040/<C>/artifacts/`, plus `~/.cache/rel040-cut/`.

## Open after the tag (first change: 0.5.0.dev0, envelope working form, G10 re-take)

- R-1009 / R-912: widen `scripts/v0_2_gate.py:129` `LIMITATION` for `L-X04-*`, `L-S11-*`, `L-E01-1` and `L-X10-1`.
- Restate envelope row L-WS-2 for ADR 0070's explicit warm-start source.
- `m03_ipopt_inventory.py`: `pynumero_asl_lookup_without_pyomo_config_dir` records host state. It needs a design-lane
  ruling before TR09's first RC cut.
- Design-lane notes:
  - RP.S22 and V03.A04 decisions (c0e5de9b, 2650fb8a);
  - the old-ledger tests now read at the tags (ede589d0);
  - RRC D-45, MSG F1, `J/(mol*K)` vs ADR 0062, the X04 notes, the `pytest -m nlp` mpmath collection issue, REL040
    review N-4;
  - the 67 stale worktrees on TRS2.
- Load note: during step 12 (G11's fixed 8-worker pool) TRS2's whole-machine load reached 52.8, against a limit of about
  36.

Standing rules: CLAUDE.md, plus `docs/NEW_HOST_SETUP.md`. Never set `reviewed` on your own package. Stage named paths
only. No credentials are copied between hosts.
