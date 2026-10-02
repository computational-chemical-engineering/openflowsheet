# Fable brief — K04: the verifier, its certificate, and ADR 0007

**To:** `fable-specifier`
**From:** the Opus session (Opus 5)
**Date:** 2026-09-22
**Deliverables:** `docs/derivations/K04-certificate-spec.md` **and**
`docs/adr/0007-reproducibility-certificate-policy.md`
**Gate this closes:** **G04** — "balances, phase transition, bad spec and numerical failure"

---

## 0. Why one brief and not two

Plan §4.1 names ADR 0007 "reproducibility **and certificate policy**". K04 is the certificate.
Splitting them would spend two Fable passes on one subject and, worse, would ask you to rule on
what a certificate claims across a platform change before the certificate exists. So: one pass,
two documents — the ADR fixes policy, the specification fixes the recipe K04 implements and is
judged by.

The reproducibility half is not hypothetical. A second CI architecture went live on 2026-09-22
and has already forced three reclassifications of what this project can promise. Those are §4,
and they are the most useful thing in this brief.

## 1. The question

**What must be true of a solved state before this project says `VERIFIED`, how is each part of
that established independently of the solver that produced it, and what survives a change of
machine?**

Six things I need decided. (1)–(4) are the specification, (5)–(6) are the ADR.

1. **The independent checks.** Blueprint §8.1: "Final verification reconstructs the original
   equations after aliasing, tearing, and transformations. Reevaluate without approximate caches
   or unauthorized substitutions; **independent balance evaluators are required**." What are the
   SYN-001 checks concretely, and in what sense is each independent of K02's units and K03's
   residual — a separate evaluator, a separate derivation, or only a separate code path?
2. **The [A08] regularity screen**, concretely. Blueprint §8.1 demands a
   factorization-based reciprocal-condition estimate on the **unregularized target Jacobian at
   the final state**, explicitly *not* U-diagonal inspection, with a bounded rank-revealing
   QR/SVD fallback and `INCONCLUSIVE` retained when budget forbids. Which matrix exactly, for a
   torn problem? The 3×3 tear derivative, the 44×44 inner block, or the assembled 49×47 system
   after the two pressure eliminations?
3. **Injected false success.** G04 and plan §4.1 require that a *deliberately wrong* answer be
   rejected. What are the registered injections, and what must each produce?
4. **The verdict vocabulary and partial-state labelling**: when `VERIFIED`, `RELAXED`,
   `UNVERIFIED`, `FAILED`; and what a certificate says about a state that is partially checked.
5. **The reproducibility classification** — which recorded artifacts are R0 Structural and which
   are R1/R2 floating-point — and **what "the declared numerical policy" is**, since blueprint
   §8.3 uses that phrase for both R1 and R2 and no document declares one.
6. **What a certificate claims across a platform change**, and what K05's replay reports in each
   of the blueprint's three cases (exact replay / compatible reproduction / inspected archived
   results).

## 2. Why this needs Fable

Every part is a claim about correctness that other packages are judged against, and the
failure mode is specifically an *agreeable* verifier. Blueprint §8.1 says it plainly: "No finite
test suite constitutes a proof that the verifier has no defects." A verifier written by the same
session that wrote the solver, against the same understanding, is the injected-false-success
risk in person. I want the recipe from someone who did not write K03.

## 3. What exists now

K03 is complete and merged: **G00 closed**, **G01 met with limitations**, the Fable review
returned with five must-fixes and all five closed. Evidence:
`evidence/K03/c806f83fd3fb0e71967235000fb517fc1c26efd4/manifest.json` — 15 checks pass, 1
unsupported, 1 not applicable. Gate green on both architectures at **1187 tests**.

| Path | What it is |
| --- | --- |
| `docs/derivations/K03-solver-spec.md` | The solver specification, and the model for what I am asking you to write |
| `docs/reviews/K03-review.md` | Your own review of K03 — §9 lists what K04 inherits |
| `src/process_runtime/orchestrator/tear.py` | `R(t)`, the Schur complement, the inner-consistency check, `build_plan`, `solve_tear` |
| `src/process_runtime/orchestrator/rank.py` | Structural alias elimination and its certificates |
| `src/process_runtime/numerics/linear.py` | ADR 0004's single SuperLU call and its recorded evidence |
| `tests/reproducibility.py` | The interim comparison rule and the measurements behind it |
| `benchmarks/syn001/reference_values.yaml` | Your 20-digit references |

**What K03 deliberately does not do, and hands here.** Every checkpoint is `unverified`; K03
issues no certificate at all, because a solver certifying its own answer is the failure §8.2
warns about. Two findings of your K03 review are explicitly K04's inheritance:
`Checkpoint.full_state_sha256` and `jacobian_identity` have no writer, so **A35's
factorization-identity check has nothing behind it** — and [A08] needs exactly that, since it
forbids reusing a factorization that does not belong to the final Jacobian. And **§8.2's
admissibility check on the converged answer (A26, A27) is unimplemented**, which matters because
it is the only guard on the branch the flash-only attempt signature deliberately does not
freeze.

## 4. What two architectures have already measured

This is the section that should save you the most time. All of it is from CI on the registered
pair (`ubuntu-latest` x86-64, `ubuntu-24.04-arm` aarch64), same commit and same lock file, plus
local one-ulp perturbation studies.

### 4.1 What is bit-identical across architectures

Every `state_sha256` up the traversal — so **every property evaluation, every flash iteration
and the mixer's inner Newton reproduce exactly across instruction sets**. Also the event
sequence with its kinds, attempts, iterations, signatures, outcomes and messages; the unscaled
residuals; `residual_calls`, `jacobian_calls`, `factorizations`; and every id, scale, bound,
certificate and estimate in the plan.

### 4.2 What is not, and why each one surprised me

| Quantity | Measured | Reclassified as |
| --- | --- | --- |
| Converged `state_sha256`, `merit`, `step_inf_scaled`, `u_diag_*`, `residual_normalized` | 1–3 ulps between architectures; `13c05f70…` against `44c1c052…` | R1/R2 floating point. **The non-portability enters at the SuperLU factorization, not in the thermodynamics** |
| `property_calls`, `requested_evaluations`, `cache_hits` | One ulp on the OFF-B start moves them 476→612, 1067→1385, 591→776 — a 13% spread — while outcome, attempts, iterations, restart and all 27 events are invariant | Not reproducible at all. Sums over hundreds of *inner* iterative solves, each free to take one more step |
| `nnz(L)`, `nnz(U)` | Nine one-ulp perturbations give **six distinct** `nnz(L)` sequences on one machine, including the 103-against-104 aarch64 reported | Pivot-determined. It looks structural and is not: the pattern is the one SuperLU produced *after* partial pivoting, and §8.3 excludes adaptive floating-point decisions |

### 4.3 The finding that is a design problem, not a comparison problem

K03 §11.2 budgets on `property_calls` and assertion A15 registers `counters.property_calls == 20`
exactly on exhaustion. Section 4.2 says that quantity has a natural spread of ~130 from a
one-ulp input change. **A budget of 500 on a solve whose honest range is 476–612 decides close
to arbitrarily**, and blueprint §8.3's "operation-count budgets support deterministic tests"
does not hold for any solve that damps. A15's exactness is fine — a hard cap is deterministic by
construction — but the budget as an instrument is weak. I think this needs a ruling and possibly
a different budgeted quantity; `requested_evaluations` is no better (it moves too).

### 4.4 Interim rule, which I am asking you to replace

`tests/reproducibility.py`: structure compared exactly; digest *values* not compared but
required to be 64 lowercase hex, empty, or null; the counts in §4.2 checked for being counts and
never for value; floats at `rel_tol = 1e-9` with an absolute floor taken from **the threshold
each quantity already has registered** (ADR 0004 D3.2's `1e-12` for `residual_normalized`, §3.4's
`1e-10` for `eta`, ADR 0001 D6's `3.1e-8` for `residual_inf_unscaled`, half its square for
`merit`). The reasoning is that below its registered threshold a quantity is not a measurement
but the absence of one, and two absences agree.

**Where I am least confident:** that last step, and that a quantity with no registered threshold
falls back to an invented `1e-24`. Also that I have reclassified three things in one day, each
on a measurement, and each time the check I was confident in turned out to be asserting
something the authority documents already excluded. Treat §4.2 as measured fact and my
classification of it as a recommendation to confirm or overturn.

## 5. Already decided, and not open

- **Blueprint §8.1** in full, including [A08] and [A09] — quoted at length above and in the
  repository. [A09] in particular: an energy balance using the same property package "is not an
  independent validation of enthalpy correlations"; record the shared provider/data hashes.
- **Blueprint §8.3**: the four classes, and "adaptive floating-point decisions are not included
  in a cross-platform bitwise promise".
- **ADR 0008 D2.1**: `state_sha256` covers exactly the dense vector `x`, and **"no test may pin
  a digest value"**. K03 violated this for a week; a test now enforces it behaviourally.
- **ADR 0002** canonicalization; **ADR 0004** the SuperLU configuration and its recorded
  evidence; **ADR 0001 D6** the registered tolerances; **ADR 0006** distribution, Q1 and Q2 both
  now closed by Frank.
- **The plan §2.1/§2.2 freeze.** K04 adds `SolutionCertificate` and `FailureBundle` (plan §2.2
  row K04/K05). Changing one of K03's five is a migration and you should say so explicitly.
- **R-010 to R-015** in `docs/decision-register.md` — K03's settled choices, including why the
  tear is three-variable and why the attempt signature covers the flash only.
- The two-platform CI pair is `ubuntu-latest` + `ubuntu-24.04-arm`; Frank chose it on 2026-09-22
  from plan §4.2's registered set. Not open, and not a third platform.

## 6. Already tried and rejected, with evidence

- **Byte-exact document comparison.** Wrong twice over: fails across machines (§4.2) and pinned
  39 digest values against ADR 0008 D2.1.
- **One universal absolute floor** beneath a relative tolerance. aarch64 reported
  `residual_normalized: 1.11e-16 against 0.0`; no relative tolerance reconciles a zero.
- **Treating `nnz(L)` as structural** because it is an integer count of a sparsity pattern. §4.2.
- **U-diagonal inspection as a rank test.** Already rejected by blueprint §8.1 and by ADR 0004
  D3.4, which makes the `|U_ii|` screen recorded and never decisive. K03 honours that; the
  measured ratio on real solves is 3.99e-2. Do not resurrect it for [A08].
- **A finite-difference derivative as anything but an oracle.** Plan §4.2 demotes it and K03
  measured why: at `t*` the central stencil leaves the mixer's domain on two of three columns,
  because `t*` is the saturated boundary. Away from it, it agrees with the exact derivative to
  3.3e-11 and is retained as an independent check. It may be useful to you for independence.

## 7. How the answer will be verified

The gate is `PATH=.venv/bin:$PATH ./scripts/check.sh` on both architectures, currently green at
1187. K04's own evidence manifest will measure every number it records, as K03's does. The
existing contract in `tests/test_k03_schemas.py` must keep passing: a changed scale, a renamed
row, a different elimination, a lost event, a changed solver counter and a changed outcome all
still fail.

For the verifier specifically I will want registered cases with *analytic or independently
derived* expectations, not self-generated ones — the repository's standing rule is that
self-generated outputs are regression fixtures and correctness fixtures need an independent
expectation.

## 8. Deliverables

**`docs/derivations/K04-certificate-spec.md`**, in the shape of your K03 solver specification:
numbered sections, registered states with values, numbered falsifiable assertions (A-numbers)
each with its tolerance and whether it is exact or toleranced, and a machine-readable
`benchmarks/k04/reference_values.yaml` where numbers are needed. It must cover questions (1)–(4)
of §1, and say for each check what it is independent *of*.

**`docs/adr/0007-reproducibility-certificate-policy.md`**, house form (status, context, numbered
decisions, what it does not establish, open questions with recommended defaults, a
changing-this-ADR clause), covering questions (5)–(6) and §4.3.

## 9. Escalate to Frank rather than choosing

Frank has asked to be consulted directly if the *design* is in doubt — not for routine
judgement, but where the answer turns on something only he can settle. If you hit one of those,
**stop on that point, write it in the document under a heading `FOR FRANK`, state the options
and your recommended default, and continue with the rest.** I relay them verbatim; do not
silently pick. The kinds of thing that qualify: a scientific requirement that would have to
change; a promise about correctness whose strictness is a project-value judgement rather than a
technical fact (how strict `VERIFIED` should be is plausibly one); anything needing compute,
data rights or an outward-facing action; and any point where you would be reversing a decision
Frank himself made.

## 10. Out of scope

Replay bundle mechanics and the `RunManifest` field set (K05). Transactions, CLI, the v0.0 gate
(K06). Generalizing the phase-attempt contract (T03) or rank diagnostics (T06). A third
platform. Re-deriving the SYN-001 references. Writing production code — this pass produces the
documents K04 is implemented against and judged by.
