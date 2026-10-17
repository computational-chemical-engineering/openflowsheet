# Re-judgement brief: `0.2.0a1` at C_α² — V13, V17, W21 after Frank's answers (spec §19.2, §19.8 action 10)

**Task.** One `verdict` agent re-judges the three gates that were `BLOCKED` on Frank's registered answers, at
**C_α² = `cc73219a77f6a54579c8acb151ed6fae228c8a4c`**, in `docs/reviews/V02-alpha-verdicts.md` (Judged 2026-10-16).
Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-gate`, branch `wp/V02-alpha-gate`.

**The answers (recorded in ADR 0028, `docs/adr/0028-v0.2-pre-release-policy.md`, decisions table and D3 table).**
Frank, 2026-10-17, verbatim: "Accept the defaults" — given after he was shown the four questions in plain words:
1. N3: the claim set `v0.2-alpha-gate-v1` (V11–V20 re-judged, plus W21 and W22; nothing of W23–W27).
2. V17 carry: carry `v17-c2`'s agent evidence (alternative was a new campaign, ≈ USD 10).
3. M02 N1: publish the external reactor subprocess, unconfined with the user's privileges, stated as "not a sandbox".
4. V14 (b): accept the PTC failure again (D3 row).
Each cell reads `accepted, 2026-10-17 — Frank, verbatim: "Accept the defaults" (the default in this row)`.

**What to do (§19.2, R-371).**
- Do not change `Judged`. Add exactly one line directly below the header:
  `**Re-judged:** 2026-10-17 (V13, V17, W21)` (or the subset whose verdict you can now give; strictly table order;
  T8's regex in §19.2 item 3), using today's date if later — it must be ≥ every answer date it reads.
- Change only the V13, V17 and W21 rows of the one `Verdict` table, in place. Add a `## Re-judgement` section: for each
  gate, the clauses judged again (V13 (e), V17 (a), W21 (c); and W21 (f4)'s notes half, which reads the `## v0.2.0a1`
  section of `CHANGELOG.md` at C_α² per §19.5), the answers read (item and date), and the evidence at C_α². The verdict
  document's own table "Frank's answers each row waits on" says what each answer unblocks and what still must hold
  (M07a.A37 and A51 at C_α² for V13 (e) and V17 (a)).
- V14 stays `FAIL`; its D3 acceptance makes it releasable (D2.3) and is not a re-judgement. No other row changes.
- Never set `reviewed`; never move a tolerance, band or classification rule. If any clause cannot now be met, say so:
  a failed clause stays failed.

**Then** run `scripts/v0_2_gate.py --rc cc73219a77f6a54579c8acb151ed6fae228c8a4c` once (with
`PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=$PWD/src`) and report what it prints: the expected
remaining refusals are the build-lane parts of action 10 (§9.2 step 5, A52 and A64 at the candidate, manifest re-run,
§9.2 step 7) — say exactly which it names.

**Rules.** Read narrowly (grep -n / sed -n); stay under ~150k context. Commit the verdict document (named path; trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`),
push `wp/V02-alpha-gate`. No gate run needed for a review document. Report ≤ 250 words: per gate the new verdict and
why; the gate script's output.
