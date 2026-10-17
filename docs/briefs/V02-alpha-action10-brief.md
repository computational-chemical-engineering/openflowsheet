# V02 alpha action 10, build part (build lane, opus-engineer): §9.2 steps 5–7 at the candidate

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-gate`, branch `wp/V02-alpha-gate` @ `c52039b` (pushed).
Work only there. **Do not merge into main** (see "Main" below).

## State
- C_α² = `cc73219a77f6a54579c8acb151ed6fae228c8a4c` (branch `wp/V02-alpha-rc2`); RC steps 1–12 PASS; M07a manifest
  `evidence/M07a/cc73219…/manifest.json` `tested` (38 pass, 6 unsupported: A52, A60–A64).
- Frank's four answers are in ADR 0028 (`accepted, 2026-10-17 …`, `e4cad68`).
- Verdict `docs/reviews/V02-alpha-verdicts.md`, re-judged 2026-10-17 (`c52039b`): V11–V13, V15–V20, W21, W22 PASS;
  V14 FAIL (b), accepted in D3. Findings: R1 ADR 0028 status still Proposed; R2 neither notes nor envelope say V17's
  agent evidence is carried from an earlier surface (one sentence in step 5's notes).
- `scripts/v0_2_gate.py --rc cc73219… ` at `c52039b`: NO, 3 reasons: W21 and W22 have no verdict in the ledger (D2.1);
  ADR 0028 not Accepted (§7.2 item 7).
- This branch's D2.4 paths (`v0_1_gate.TREES`) equal C_α²'s exactly; keep it so (touch none of `src`, `schemas`,
  `benchmarks`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`). If a step seems to
  need one, STOP and report.

## Do (spec `docs/derivations/V02-alpha-release-spec.md` §9.2 l.781–, §19.4 l.1573, §19.5 l.1592, §19.8 action 10)
1. **ADR 0028 Accepted** (§9.2 step 6: "ADR 0028 is marked Accepted"; its own Status block l.3–8 states the conditions):
   status line → Accepted, 2026-10-17, with the reason; register entry for it in `docs/decision-register.md` on this
   branch — the next free number above R-450 that is unused on this branch, on `origin/main` and on `origin/wp/M05`
   (follow the pattern of R-381 / B6 `758a902`).
2. **Step 5:** the ledger (M07a.A64) with every claimed gate's verdict word including W21 and W22, as the verdict
   document gives them; the `## v0.2.0a1` section of `CHANGELOG.md` (M07a.A52, §19.5's phrases from the YAML), adding
   R2's sentence (V17's agent evidence is carried from `v17-c2`'s surface, not re-measured on v0.2's), then
   `v0_2_gate.py --rc cc73219… --markdown` and the section's gate table equal to it (A52 (c)).
3. **Step 7, first half:** at the resulting candidate commit, `tests/test_m07a_changelog.py` runs with no skip and A64's
   test runs; re-run `scripts/m07a_evidence_manifest.py` so A52's and A64's results carry `judged_at` = the candidate
   (status still from A00–A51 and A53, §19.4). Then
   `PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=$PWD/src python scripts/v0_2_gate.py --rc cc73219a77f6a54579c8acb151ed6fae228c8a4c --candidate <this branch's head>`
   must end `v0.2.0a1 tag may be proposed: YES`. If it does not, report its reasons verbatim; do not work around them.

## Main (context only; not yours to fix)
`main` has taken D2.4 changes since C_α² (M02 follow-up, M03, M04 CI fix; M05 soon), so main's head cannot be the
candidate as §9.2 step 7 assumes. ADR 0028 names the alternative (dispatch from a tag Frank pushes). The session is asking
Frank. Your job ends with YES at this branch's head.

## Rules
- Full gate before every commit, background, read logs only on failure:
  `mkdir -p evidence/M06/W27 && ln -s /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts evidence/M06/W27/artifacts`
  then `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`; remove the link
  afterwards; never commit it. Last gate on this branch: 8635 passed, 33 skipped.
- Never set `reviewed`; never move a rule. Named paths only. Trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`.
  Push `wp/V02-alpha-gate`. Context cap ~150k.
- Report ≤ 200 words: R-number, commits, the gate script's final line at the candidate, gate counts.
