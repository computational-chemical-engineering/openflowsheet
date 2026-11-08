# Specifier brief: the certificate's derivative-witness step at small and held-zero flows

Status: brief, 2026-11-08. Not a roadmap package; a design-lane follow-up raised twice in 0.4 (X10 review M-1 →
L-X10-1; OPT D-42). Deliverable is a specification amendment (K04 certificate spec) with an identity plan — the build
lane implements later, and any move of a registered certificate needs Frank's approval.

## The question

How should K04's derivative witness choose its finite-difference step and stencil so that it does not fail on states
whose small or exactly-zero (held) flows make the registered step leave the domain or dominate the truncation error —
while every registered certificate either stays byte-identical or moves only by a stated, approved re-registration?

## Measured facts

1. **L-X10-1 (small flows, `pr-c1-v1`).** `c1.reactor_surrogate` on `benchmarks/m04/c1-surrogate.json` (policy
   `T06-revision-v2`): CONVERGED, **UNVERIFIED**, `derivative_witness.on_pattern` = 0.109 vs tolerance 1e-7. Witness step
   h = `FD_RELATIVE_STEP` (1e-5) × column scale = 3e-5 mol/s; per-tube flows 1.4e-4 … 4.9e-3 mol/s, so h is 14–21 % of
   the flow. J − FD falls exactly 4× per halving of h (0.109 → 4.3e-4 over four halvings): pure O(h²) truncation, the
   AD Jacobian is consistent. Review `docs/reviews/X10-review.md` (M-1, lines ~20–65); probe scripts in the session
   scratchpad were `surr.py`, `surr2.py` (not committed).
2. **OPT D-42 (held zero sides, Wilson γ–φ).** On `wilson-ig-v2`, K04 is UNVERIFIED at every single-phase held split
   measured (GP-C3's heater held LIQUID at 340, 345 K; VAPOR at 365–385 K): the stencil steps the held, exactly-zero
   phase side negative → `witness_stencil_invalid_trial_state(S4.liq.CH3OH)` / `S4.vap.CH3OH` plus
   `derivative_limitation`. Log `wp/OPT` `docs/OPT_DECISIONS.md` D-42.

## Current state (anchors on main)

- `src/openflowsheet/verify/checks.py:850` `FD_RELATIVE_STEP = 1e-5`, `:854` `DERIVATIVE_TOLERANCE = 1e-7`, `:897`
  `derivative_witness(...)`: central differences of the compiled function vs its AD Jacobian, step
  `FD_RELATIVE_STEP * scaling.column[name]` (`:957`), scaled into the checks `derivative_witness.{on,off}_pattern`.
- Existing exceptions: **R-281** (`docs/decision-register.md:6315`; amended by R-345) — exactly-zero `pr-c1-v1` stream
  flows `<S>.n.<c>` are not differenced (`unstenciled`), recorded as the `derivative_witness_partial` limitation;
  **R-831** (S11 rulings item 2; ADR 0013 Amendment 3 item 7) — on a Wilson basis the set Z of `one_sided_columns` uses
  the forward five-point stencil at the same h. `:1017` `witness_skipped_columns`.
- Spec: `docs/derivations/K04-certificate-spec.md` (§4.8 the witness), `docs/derivations/K04-F9-spec.md`; ADR 0013.

## Constraints

- No relaxed checks: the tolerance 1e-7 and the meaning of the two checks stay; the fix is in how the reference
  derivative is formed, justified by truncation/round-off analysis, not by loosening.
- F0 corpus identity (`scripts/corpus_identity.py --check`, M1–M9): every registered certificate's bytes. Prefer a rule
  that leaves every currently VERIFIED certificate byte-identical (e.g. applies only where the registered step is
  invalid or demonstrably truncation-dominated by a stated test); if any registered certificate must move, list them
  exactly and say why — that is a Frank decision.
- The residual and Jacobian describe the same function; the witness is an independent check of the AD Jacobian, so the
  new stencil must remain independent of the AD path.

## Genuinely open

1. Step selection: state-relative (e.g. h_j = max(ε·|x_j|, floor) with a stated round-off/truncation balance), a
   Richardson/extrapolated estimate, or extending R-831's one-sided set Z to held-zero sides on any basis.
2. Which columns are "held zero" (OPT's A-2 zero subsystem and held phase sides) and whether the witness can know them
   from the certificate's own data.
3. The identity plan (what moves, if anything) and the tests: L-X10-1's surrogate case verifying, GP-C3 held splits
   verifying, every registered certificate unchanged (or the exact list that moves).

## Deliverable

An amendment to `docs/derivations/K04-certificate-spec.md` (numbered, with the replaced text quoted), numbered
falsifiable assertions and reference values (independent: e.g. analytic derivatives of a small case at known states),
an ADR draft if the policy change needs one (next free number after 0072; Proposed), register lines drafted
unnumbered, and a plain-words question for Frank if any registered certificate moves. Commit on **main** (docs-only,
named paths, message `docs: witness-step specification`, with the session's Co-Authored-By / Claude-Session lines).
Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; single small probes only, `OMP_NUM_THREADS=1`; a full gate is running — no other.

## Out of scope

OPT/RRC/X10 code; the regularity (rank) check; tolerances; style.
