# Fable review brief — K03, the nonlinear solver

**To:** `fable-reviewer`
**From:** the Opus session
**Date:** 2026-09-21
**Subject:** independent review of the K03 implementation against `docs/derivations/K03-solver-spec.md`
**Closing:** gate **G01**, and with it work package K03

---

## 1. The question

**Does the K03 implementation compute what the specification says it computes, and does its
evidence establish what it claims?** Two halves, and the second matters as much as the first:
this package's numbers are all self-generated except where an mpmath reference or an analytic
identity stands behind them, so "the tests pass" is not the finding I am asking for.

Concretely, five things I want a verdict on:

1. **Is `dR/dt` the derivative of `R`?** The residual is K02's sequential traversal; the Jacobian
   is the Schur complement of the assembled lifted system. They are the same function only where
   the inner rows hold. I check that (η ≤ 1e-10) and I check the result three ways. Is the
   argument airtight, or is there a state where the check passes and the derivative is still of
   something else?
2. **Is the structural elimination sound?** Two pressure rows are removed before any numerics,
   with a two-probe certificate. Is a two-probe certificate a certificate?
3. **Is §9's phase-attempt contract implemented as specified, and is the contract itself right
   for SYN-001?** In particular the decision that the attempt signature covers the flash and only
   the flash.
4. **Does the evidence establish G00 and G01?** I believe G00 is closed and I state plainly that
   the registered variants do not exercise the globalization at all. Is that limitation stated
   strongly enough, and is the substitute coverage (OFF-A, OFF-B, seven synthetic seeds) actually
   sufficient for G01's "damped Newton" half?
5. **What have I got wrong that no test I would write could find?** This is the part I cannot do
   for myself.

## 2. Why this needs Fable

Everything in §1 is a correctness question about derivatives, active sets and rank at a
saturation boundary, and the specification under review is Fable's own. The one defect I found in
that specification (§7.2's eliminated-row signs, below) I found only because a registered
assertion disagreed with my measurement — which is exactly the class of thing an independent read
catches and a test suite does not.

## 3. What to read, in this order

| Path | Lines | What it is |
| --- | --- | --- |
| `docs/derivations/K03-solver-spec.md` | 603 | **The specification you are reviewing against.** Fable-authored, 2026-09-21 |
| `evidence/K03/19764e1afba6e95cda84780019bba789c7a60085/manifest.json` | — | Every claim I make, with the measured number behind it |
| `src/process_runtime/orchestrator/tear.py` | 491 | `R(t)`, the Schur complement, the consistency check, `build_plan`, `solve_tear` |
| `src/process_runtime/orchestrator/rank.py` | 225 | Structural alias elimination and its certificate |
| `src/process_runtime/orchestrator/attempts.py` | 415 | §9's bounded attempt controller and the phase wall |
| `src/process_runtime/numerics/newton.py` | 492 | §5's damped Newton, the Armijo search, the bound rule |
| `src/process_runtime/numerics/scaling.py` | 187 | §7.3's scales from the registered nominals |
| `src/process_runtime/numerics/linear.py` | 148 | ADR 0004's single SuperLU call |
| `src/process_runtime/orchestrator/trace.py` | 395 | The five recorded metadata types |

Commit range `26285e7..40ae9df` on `main` (merged), plus `203e05d` and `6f68d74` for M1/M2.
Tests: `tests/test_k03_{scaling,linear,newton,rank,tear,attempts,schemas}.py`.

Gate: `PATH=.venv/bin:$PATH ./scripts/check.sh` — green, **1166 tests**.

## 4. What I built, in one paragraph per decision that could be wrong

**The residual is the three-variable tear, not the lifted 47-variable system** (register R-010,
spec §3.1). `R(t) = G(t) − t` where `G` is K02's sequential traversal and `t` is `S6`'s three
component flows. The reason is not aesthetic: in the lifted form both trivial phase splits are
*exact* roots of every row, so a bound-aware Newton can land on one and report a converged answer
with a duty 8237.85 W wrong. That is K02's finding 3 and it is measured, not feared. The traversal
cannot reach those points because each unit selects its own phase state.

**`dR/dt` is the exact Schur complement** of the assembled 49×47 Jacobian, taken in scaled units
and transformed back out (`tear.py:274-316`). The tear rows evaluate `−R`, so the derivative of
`R` is the negation — a sign I got from the row definition and then checked against three
independent expectations rather than trusting.

**The consistency check is what makes that honest** (§3.4, `tear.py:319-340`). The Schur
complement is the derivative of the *lifted* function at `x(t)`; the residual is of the
*traversal*. Every Jacobian evaluation therefore also evaluates the inner rows and requires
η ≤ 1e-10 in scaled units, and an attempt whose check fails ends `INNER_SOLVE_INCONSISTENT`
naming the worst row rather than stepping on it. Measured worst η: **2.0e-16**.

**Two pressure rows are eliminated structurally, before any numerics** (§7, `rank.py`). The
declared rows over-determine the pressure network by two (K02 finding 2). The eliminator builds a
union–find forest over pressure columns with ±1 coefficients, treats a specification row as an
edge to a constant node, and emits for each eliminated row a certificate: the signed combination
of retained rows it equals, and the constant mismatch, which must be identical at two probe
states shifted by a non-uniform pressure offset. Measured mismatch at both registered rows: 0.0.

**The attempt signature covers the flash and only the flash** (§9.1, `attempts.py:40-70`). I want
this challenged. The map is `(vapor_signature, liquid_signature) → regime`. Freezing every
stream's regime instead is what I built first, and it is measurably wrong: the nominal case's
one-step landing on `t*` is then *rejected as a phase change*, because the heater outlet flips
TWO_PHASE → LIQUID along that step. So the signature is over the selections the residual depends
on, not over every selection made anywhere. Is that the right general principle, or is it right
here for a reason that will not survive T03?

**The plan precedes the numerics** (D06, §12.2). `SolvePlan` holds the partition, the eliminations
and their certificates, the scales and their provenance, the bounds and the initializer order.
It is built before the initializer runs and `plan_built` is the first event of every trace.

## 5. Constraints and invariants, so they are not relitigated

- Plan §2.1 interfaces and §2.2 schemas are **frozen**. K03 added five (`SolvePolicy`,
  `SolvePlan`, `SolveEvent`, `AttemptContext`, `Checkpoint`); changing one now is an ADR.
- **ADR 0001** D4 sign conventions (duty positive into the unit), D6 registered tolerances.
- **ADR 0004** fixes the SuperLU options verbatim; `linear.py` asserts them against the ADR text.
- **ADR 0008** D1 (no time at the boundary), D2 (`state_sha256` covers exactly `x`), D1.4 (the
  workspace is inert and is never serialized).
- **R-014**: `t⁰ = G(0) = (1−r)t*` is *the* registered initializer; `r F_i` is retired. Frank's
  call, not open.
- **R-012**: K03 §9 is the interim normative text for the phase-attempt contract; ADR 0005 is
  T03's. A finding that §9 is wrong is in scope; a finding that it should be an ADR now is not.
- No `reviewed` status on any manifest — human sign-off only.

## 6. Already tried and rejected, with the measured evidence

This is the section that saves your budget. Each of these I walked down and came back from.

| Tried | Why it is not there |
| --- | --- |
| Newton on the lifted 47-variable system | Both trivial splits are exact roots; duty 8237.85 W wrong at the once-through variant (K02 finding 3) |
| Finite-difference `dR/dt` as the derivative path | Plan §4.2 demotes it, and it *cannot work at `t*`*: `t*` is the mixer's saturated domain boundary and the central stencil leaves the domain on two of three columns. It is retained as an oracle away from `t*`, where it agrees to 3.3e-11 |
| A seven-stream attempt signature | Every variant restarted needlessly and the same signature appeared twice in one solve (see §4) |
| Inferring iteration and step length for the phase wall from outside the Newton core | OFF-B ground through 11 iterations where §9.3's rule closes the attempt at 2. Replaced with an `IterationObserver` the core drives |
| Reporting `policy.max_attempts` on exhaustion | It hid an unbounded loop, because the two coincide exactly when the loop *is* bounded. Now reports attempts actually run |
| One probe state for the elimination certificate | A single state cannot distinguish a constant mismatch from a coincidence; `test_one_probe_state_is_not_a_certificate` pins this |
| `np.min(diagonal, initial=0.0)` for the `|U_ii|` screen | Returns 0.0 for any positive array, so the screen was a constant. Found because my measurement disagreed with ADR 0004's registered 7.1e-3 |

## 7. One defect I found in the specification, already corrected

**§7.2 recorded the second eliminated row's signs negated.** It is invisible at a consistent
state, where the combination is zero either way. At the registered 150 kPa conflict it gives
`+50 000 Pa` where assertion A30 registers `−50 000`. The true combination is
`+FEED-P − MIX-pressure:0 + MIX-pressure:1 − FLASH-P:liquid`. I confirmed it three independent
ways — linear algebra on the coefficient matrix, evaluation at the conflict state, and graph
traversal of the union–find path — and corrected §7.2 in place with a dated note. The specifier
agent subsequently found the same error in its own generator's data block and fixed that too.

I mention it because it is the only place where I overrode Fable text, and you should check that
I was right to.

## 8. The measurements, so you do not have to rerun them

All five registered variants, from the registered initializer, at the manifest commit:

| Quantity | Worst | Against |
| --- | --- | --- |
| Tear `\|t − t*\|` | 3.9e-14 mol/s | Fable's 20-digit recycle; registered tolerance 3.1e-8 |
| Vapour product | 2.7e-15 mol/s | the registered products |
| Duty | 1.8e-9 W | `Q_heater`, `Q_flash`; tolerance 1.01e-3 |
| Overall balance | 2.0e-15 mol/s | fresh feed = vapour product + purge |
| `dR/dt` vs closed form | 1.6e-15 | 40-digit mpmath, at `t*` and OFF-A |
| `dR/dt` vs finite difference | 3.3e-11 | an oracle sharing no route with the assembled Jacobian |
| Affine-ray identity | 1.9e-16 | `J(t*) t* = −(1−r) t*`, from K02's metamorphic relation |
| Inner consistency η | 2.0e-16 | registered 1e-10 |
| Linear residual | 1.1e-16 | ADR 0004 D3.2's 1e-12 |
| `min\|U_ii\| / max\|U_ii\|` | 7.13e-3 | ADR 0004 D3.4's registered 7.1e-3 |

Effort: **one attempt and at most one accepted iteration per variant.** OFF-B, the registered
phase restart: 2 attempts, LIQUID then TWO_PHASE, 2 + 2 iterations, matching §13.3 number for
number.

## 9. Where I am least sure

Ranked. Spend your time here.

1. **Whether the inner-consistency check is sufficient, or merely necessary.** η ≤ 1e-10 says the
   inner rows are satisfied at the reconstructed state. It does not say the reconstruction is the
   *same* inner solution the traversal used — only that it is *an* inner solution. At a saturated
   boundary with a nearly singular inner block, could those differ while η stays small?
2. **Whether the elimination is valid at every state the solver can reach**, not only at the two
   probes and the five variants. The forest is built once, from the structure, at the initial
   guess. `test_the_elimination_is_the_same_at_every_registered_variant` checks the variants. It
   does not check an arbitrary iterate.
3. **The signature question of §4.** Right principle, or right answer for a local reason?
4. **Whether G01 is really closed by seven synthetic seeds.** The Newton half of G01 is exercised
   entirely off the real problem, because the real problem is affine along the ray it is solved
   on. I think that is honest and sufficient; it is also exactly the shape of an argument that
   turns out not to be.
5. **`SolveOutcome` has 15 values and no `PHYSICALLY_INFEASIBLE`** — deliberate, per §11: a solver
   may report that it failed, never that no answer exists. Is any of the 15 doing that by
   implication?

## 10. What not to spend time on

- Style, naming, docstring density, type annotations. mypy strict is green.
- Test *count*. Every module has a mutation sweep and I will tell you the numbers if you ask;
  the M6 sweep is 13/13 and is described in register R-015.
- The interface freeze mechanics, the schemas, the fixture generator, the ledger. Those are Opus
  work and were reviewed by their own gate.
- K04's territory: certificates, the [A08] regularity screen, verified states. K03 issues none
  and says so; a finding that it *should* is out of scope.
- Re-deriving the reference values. They are yours, at 40 digits, in
  `benchmarks/k03/reference_values.yaml`.

## 11. Deliverable

Write `docs/reviews/K03-review.md` with:

1. **Verdict** — one of: the implementation matches the specification; matches with the listed
   must-fixes; does not match.
2. **Must-fix findings** — each with the state or input that exhibits it, and what I should
   measure to confirm it. I will verify every one before acting; K02's review had three
   must-fixes and all three reproduced exactly as written, which is why I trust this format.
3. **Should-fix and observations**, separated.
4. **The five questions of §1, answered** — including "no finding" where that is the answer.
5. **G00 and G01** — met, met with limitations, or not met. Name the limitations.
6. **What this review does not establish.**

Do not edit source or tests; the review is a document. If you need a number I have not given,
say which and I will measure it.
