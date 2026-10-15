# Design-lane ruling: M02 WO-12a stopped at G10v3 (round 7)

Branch `wp/M02` @ `9142032`, worktree `.claude/worktrees/m02`. Round 6 rulings: `docs/design/M02-pymrm-adapter.md`
§14.5 (l.1621 on; D1 extra polish round, D2 nonfinite screen, D3 refusal tests, D4 box selection + timeout; R-303,
R-304). Build log `docs/design/M02-build-decisions.md`: D73–D76 (l.86–89, choices), **D77 (l.90)**, **D78 (l.91)**.
Uncommitted experiment evidence: `evidence/M02/wo12a-experiment/artifacts/` (`child-experiment.patch`, `g10-exp.json`,
`g11-exp.json`, `variant-v3-experiment.json`) — extract fields with python, never cat the JSON. Committed G10v3 record
and scripts in `1328da0`. Reactor spec `docs/derivations/M01-spec.md` (A41–A48).

## Facts (measured)
- G10v3 FAIL: D1's round 2 ran at all 8 points; no outlet bitwise equal to v2. Cause (D77): the group's
  `certify_convergence_1d` (runner.py:548) takes 20 more pseudo-time steps and keeps the state, so every recorded
  element defect δ was measured *after* the certificate. Right after S3, δ = 4.0e-5…8.4e-5 everywhere; records show
  2.2e-8…3.8e-8. So D1 as written tightens S3 for every evaluation — the alternative D1 rejected.
- Experiment (D78): same child, δ read after the certificate and round 2 re-certified → G10v3 met (all outlets bitwise
  v2, round 2 ran nowhere); G11v3-1 met (projection defects 1.7e-9, 1.1e-9, 2.0e-11); G11v3-2, -3 met.
- But under it no registered box qualifies: B1 12/21, B2 11/19, B3 11/19. Every zero-inert corner fails
  `nonpositive_flow` (minimum axial flow exactly 0 or −1e-25); the 773.15 K zero-inert corners' NaN is the C/Ar element
  defect 0/0 (no Ar/CH₄ in the inlet), so `max` over NaN is order-dependent; lowest-T highest-P zero-inert corners fail
  at S1; B1's 643.15 K M05 point fails at S1. Every 0.2-inert corner and every centre is `ok`.
- In-box timeout rule (D4) at this host load: 360–370 s.

## Decide
1. Move δ's measurement after the certificate (the D78 ordering)? It changes numerics only where round 2 would fire.
2. Zero-inert inlets: positivity "every axial flow > 0" cannot hold for a species with zero inlet flow; A45's δ is 0/0
   for an absent element. Rule the positivity test and the absent-element defect definition (and whether zero-inert is
   inside the shipped domain at all — the C1 loop with purge always carries inerts; check what M05/M07 need).
3. Box selection given none of the three qualifies: a fourth box, a composition dimension (inert-fraction lower bound),
   or re-judging after items 1–2. Say what M05's decision box becomes (currently [643.15, 733.15] K, N-F6; R-304 named
   [653.15, 693.15] K as the fallback) and whether the B1 643.15 K S1 failure matters for it.
4. Confirm or reverse D73–D76; and the timeout value.
Frank holds N7 (shipped domain scope; default: what the measurements select). Flag if the answer now turns on him.

## Deliverable
§14.6 of the design note + register entries (next free after R-310; check `docs/decision-register.md` on `wp/M02` and
`main`). Per item: ruling, changed acceptance with numbers, implementing WO (WO-12a′ etc.). Commit on `wp/M02` (doc
only, named paths). Note: another engineer is concurrently on `wp/M02-wo14` (driver/R3/replay) — don't touch that.
Report ≤ 300 words.
