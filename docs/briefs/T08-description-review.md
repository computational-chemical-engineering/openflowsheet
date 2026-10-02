# Brief — T08: design-lane review of the 17 MCP tool descriptions (T08.A18), plus three small rulings

**To:** `reviewer` (design lane). **From:** build lane, 2026-10-01. **Branch:** `wp/T08` at HEAD.
**Deliverable:** `docs/reviews/T08-description-review.md`. Write no code and do not edit any description or
`REVIEW.json`; do not commit. The build lane records your outcome in `REVIEW.json` under your name and date.

**Budget.** Frank is near his weekly usage limit. The texts total about 2 600 words; one pass.

## 1. What to review

The 17 files `src/process_runtime/application/bindings/descriptions/*.md` (one per MCP tool) and their record
`REVIEW.json` (sha256 and length per file; the design-lane review is `pending_design_review` for every one; Frank's
human review is recorded 2026-09-29). Review 2 (`docs/reviews/T08-review-2.md`, Ruling 13) made this design-lane
review an RC blocker. T07 context: design note `docs/design/T07-jobs-and-bindings.md` §11 (descriptions, ≤ 1500
characters, gate G15) and the application contract ADR 0019; the dispatch table `application/operations.py`.

For each description judge: (a) **accuracy** against what `dispatch` actually does today on `wp/T08` (inputs, outputs,
errors, rights) — note U05 now refuses `validate(task="optimization")` with `unsupported`/`task_unsupported(...)`
(`46dcf74`), so `validate.md:1`'s mention of `READY_FOR_OPTIMIZATION` is false; and the new offered policies
`T08-ptc-v1` (PTC, experimental) and `T08-warm-v1` (warm starts) and model `syn001.kinetic_cstr`; (b) **safety**:
nothing invites an agent to weaken verification, relax tolerances, bypass authorization or read an unverified
result as verified; (c) **sufficiency**: an agent can use the tool correctly from the text alone; (d) bounds.

**The V17 constraint.** V17 (the agent-campaign gate) is carried from T07 only while the agent-facing surface is
unchanged (Frank's F5: content-only additions keep the carry); the descriptions digest `6d13e13d…` is part of that
surface (T08.A49/B50). Any change to a description moves the digest and returns the carry question to Frank (a new
campaign costs his usage). So **classify every proposed change** as **necessary** (false, unsafe, or misleading as
it stands — must change before the tag) or **optional** (better wording; can wait for v0.2), and give the exact
replacement text for each necessary change. Approve unchanged files by their current sha256.

## 2. Three small rulings (from review 2 part A, `docs/T08_DECISIONS.md` entry "Review 2 part A landed")

1. **E7 (Ruling 7's stop condition).** On CH-UP-DP under its default route/policy the patched `region._ph_closure` is
   never called. From B31's own start (the traversal at Q = 0, as `test_b31i` uses), under `T05b-v2` or
   `T06-revision-v2`, the patched run calls it 3×, records `fallback(U-PHF, tp)` and `fallback(U-PHF2, tp)`, and ends
   typed `ACTIVE_SET_CYCLING`; the unpatched run converges. Is that start acceptable for E7's unchanged-physics test
   (and what must it compare), or is E7's evidence `null` (A33 red)?
2. **Ruling 8's exemption** (`dc3de6b`): the reachability test exempts models without an outlet port, asserting the
   set is exactly `{syn001.product_sink}` (it declares `unavailable`; a unit with no outlet is in no loop). Confirm or
   reject.
3. **S6's restriction.** Restricting the fail-closed scan rule to modules importing `orchestrator.trace` still gives
   four false positives (`application/admission.py:188`, `application/jobs/runner.py:251, 336, 409`, unrelated
   `kind=`). Build lane proposes: apply the rule to modules under `orchestrator/`, `numerics/`, `verify/` (zero false
   positives; every event producer lives there). Alternative: only `record(kind=…)` and `_initializer_event` calls,
   anywhere. Rule.

## 3. Report

Per description: approve (sha256) / necessary change (exact text) / optional change; the three rulings in one line
each; and a one-line statement for Frank of whether V17's carry is affected.
