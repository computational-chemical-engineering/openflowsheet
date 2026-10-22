# S06 — the single `reviewer` pass (design lane)

**What to review.** Branch `wp/C11` (worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/c11`), commits
`7c5ea600..6053c736` (WO-1, WO-2), against the spec `docs/derivations/S06-spec.md` (register R-601…R-607). S06 adds column
end specifications by purity, recovery and stage temperature on S02's column (`solve_column`, `solve_target`), solved by
continuation from S02's bubble-point endpoint; failures are typed (`inverse_specification_not_reached`), never false successes.

**What was run (cloud, 2026-10-22).** Manifest `evidence/S06/be4ea9897c06ea8f56bc966155b3836ab6f0d233/manifest.json`:
`implemented`, 22/25 checks pass. Non-pass: A02's I3 probe (strict xfail, Q-S06-WO1-1), the §10 deviation (Q-S06-WO2-1), gate
not run. J1–J8 and the V-sets `CONVERGED`; U1/U2 typed `HOMOTOPY_STALLED`; A09 floor ≤ 6.38e-11. Build decisions and measured
numbers: `docs/C11_DECISIONS.md` (WO-1 l.1–31, WO-2 l.33–47) — read that file, not the transcripts.

**Rule on these as part of the review (batched design questions):**
1. **Q-S06-WO1-1** (`docs/C11_DECISIONS.md:31`): register the I3 probe's feed temperature (e.g. 320 K) in the reference
   generator and spec §9, so the strict xfail becomes a pass? Or another fix.
2. **Q-S06-WO2-1** (`:44`): amend spec §10 to record J8's measured 0.182 of the state tolerance (> the 1/10 margin), with its
   conditioning (σ_min 6.1e-4; A flow ~1e-4 mol/s on stages 5–6 vs the floor 10·τ_mf) as the reason? Tolerance unchanged.

**Frank's answers, settled (2026-10-23):** Q-S06-1 — no "multiple steady states" warning for inverse specifications (C8's
duty-only rule unchanged). Q-S06-2 — the high-purity endpoint failure stays a typed result plus a §14 limitation; no second
endpoint in S06.

**Focus.** Residual/Jacobian consistency of the new rows (purity, recovery, temperature) and the `u` variable; the order
§8 item 3 before the defect clauses (`solve_target`); `lambda_state` (§7.3) source; whether the tests verify what the spec
claims (A05 via `p⁰`, A16's rule in `scripts/s06_evidence_manifest.py`). Not: style, S02 internals already reviewed
(`docs/reviews/S02-review.md`), packaging.

**Deliverable.** `docs/reviews/S06-review.md` (findings ranked; each with file:line and the fix), your rulings on the two
questions written as spec amendments (spec text + register entries, next free R-numbers), committed on `wp/C11`. Do not
implement code fixes; do not set `reviewed`. Run targeted tests only (`.venv` at `/home/frankp/Codes/OpenFlowsheet/.venv`,
`PYTHONPATH=$PWD/src:$PWD`). Context cap ~150k. Report ≤150 words. Trailer: `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`.
