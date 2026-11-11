# Verdict brief: 0.4.0, the verdicts at C (RP §4, §4.7, §9.2 step 3)

Status: brief, 2026-11-10. Design lane, `verdict` agent. **Do not spawn sub-agents yourself.** Write one document and
commit it; no code, test, tool, record or D2.4 edit (`src/ schemas/ benchmarks/ requirements*.lock pyproject.toml
MANIFEST.in README.md LICENSE NOTICE`). No tag, release, merge or push to `main`.

## The question

For each of the 17 gates that line 0.4 claims, in `claimed` order (V11–V20, W21–W26, X31): PASS, FAIL on which
clauses, or BLOCKED on what, judged only on evidence at C or carried to C by a registered carry (RP §4.1 item 3).

## Facts

- Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040`, branch `wp/REL040` (head `b2148f07`).
- **C = `84c665477b512548f38a6335f51648732b1fe5bb`**, K3 = `49a0473119a7684ddf44bdf3c59528714f49337a`, J (re-takes) =
  `e0a3d6b78f9d245ff8ed946ae954a9682f3e24c2`, journey record `b40d48d1`.
- The line file is `release/lines/0.4.json`. Its `gate_set.gates[g]` gives each gate's `criteria`, `documents`, `rc`
  (the step records) and `tests`.
- The records are under `evidence/REL040/<C>/rc/`, and `records.json` lists them. The RC record
  `docs/REL040-rc-record.md` has 68 rows, one per step and one per item, each with its summary line and record path. The
  part-3 log is `docs/RP_DECISIONS.md` `## 0.4.0 cut` (`### Part 3`), and parts 1–2 are above it.
- The results:
  - Every local step passed: 2, 6–17.
  - All 8 items passed: E01-A48, S07-F8, MR12-coolprop, MR12-lca, E01-G5-lca, E01-G6-nlp, WHEEL-DATA, PTC-R1.
  - CI push run 42790953372 is green on both architectures.
  - The `release_rc` dispatch 42791067917 passed all 13 jobs. Its artifacts are under `rc/ci/`.
  - The orchestrator's local full gate at C: `GATE PASS 84c66547: 16678 passed, 3206 skipped, 220 deselected, 3
    xfailed`. 3206 skipped is the same count as the previous TRS2 gate; the skips are mostly the CoolProp extra, the
    pre-0.1.0 history and the W27 archive.
- Re-takes (RP §7.1, R-1008; ruling `docs/reviews/REL040-s6-ruling.md`), proved before they were committed at J:
  - the five G10 records PASS, version leaves 4/7/4/3/4;
  - M05 REAL PASS: `version=0 other=0 environment=equal`;
  - M01 IDAES PASS: `platform=1 inputs=1 other=0`.
- The journey at J (RP §4.5): T* 653.15 K, BOUND_LOWER, J 0.45250. `check` ACCEPT, replay bitwise, carried to C. 71 of
  10794 leaves differ from 0.3.0's record at `2d945b5d`, all in the allowed classes.
- Step 8's surface chain at C has eight links: R-192, R-234, R-295, R-934, R-950, R-960, R-1000 and R-1010. 0.3.0 had
  three. The chain holds locally and on both CI architectures. Frank's `V17 carry` row therefore **lapsed** (lapse
  report `evidence/REL040/<C>/acceptance-lapses.txt`). He is being asked now, in his first message, whether to reuse
  v17-c2's agent evidence. Until his dated answer exists, a V17 clause that depends on the carry is BLOCKED on it, as
  0.3.0 first judged V17 (a). Say exactly which clause.
- Every other acceptance row **stands** at C: X31 (c), the claim set, M02 N1, M03 N1, and the coolprop and lca licences.
  `V14 (b)` lapsed by its `paths:` scope, because `src/openflowsheet/` changed. A failure-clause row may be re-asked only
  after `Judged` (§8.4, F-8). So judge V14 on the evidence, and if (b) fails, list it as failing. Frank's second message
  will ask for it.
- No release manifest exists yet. It is generated after your document (§9.2 step 4). Do not wait for it.

## Authority (read these sections, not whole files)

- `docs/derivations/release-procedure.md`:
  - §4 (§4.1 rules; §4.2 criteria carried; §4.3 X31's pre-registered FAIL (c); §4.4 the V17 carry; §4.5 W25; §4.6;
    §4.7 the document's form);
  - §8.3 (what a standing row does for a FAIL).
- The clause criteria that §4.2 names: the alpha spec §5–§6 with T08 §4; M07 §7.3.
- 0.3.0's `docs/reviews/V03-verdicts.md` is **for comparison only**: its table form, its basis style, and its skip audit
  (V20, R-376). Do not carry a verdict from it. With D2 deferred, every row is judged at C.
- W21 (e) needs step 12's experiment record and the files under `rc/step12/` (RP §6.4). 0.3.0 failed (e) first, because
  the G11 experiments were not kept or audited, and met it on re-judgement by V03.A34. Check that the 0.4.0 records keep
  them.

## Deliverable

`docs/reviews/REL040-verdicts.md` (= `gate_set.verdict_document`), in the alpha §6.3 form:
- the header names C once and has one `**Judged:** 2026-11-10` line; `**By:**` names the `verdict` agent;
- one table row per claimed gate, in `claimed` order, giving the verdict, the failing clauses or `—`, the travelling
  limitations and the basis;
- every clause parses under the line's grammar. Check this with `scripts/release_gate.py --line 0.4 --rc <C>`'s
  verdict-document reader if it has a dry check; otherwise follow V03's spelling exactly.

Then one section per gate with the evidence (record path and summary line), a skip audit for step 1, "What this does not
establish", and a list of Frank's answers that any row waits on.

Commit only that file (named path) on `wp/REL040` in the worktree, with the message `REL040: verdicts at C = 84c66547 (RP
§4, §9.2 step 3)`. Do not push; the orchestrator pushes.

## Stops

Report rather than choose if:
- a record contradicts its RC-record summary line;
- a criterion needs evidence that no record at C holds and that no registered carry brings;
- a pre-registered reading (§4.3, §4.4) would need to be departed from.

Trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Cap ~150k context: if you near it, commit what is judged,
write which gates remain, and stop. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/` or `~/.cache/seider4/`.

## Report (at most 25 lines)

- The verdict and failing clauses per gate.
- What each BLOCKED waits on.
- Any finding that changes a step-18 input.
- The commit sha.
