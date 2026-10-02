# K03 — decision log

Append-only. History; never read whole. The current position is `docs/K03_STATE.md`.

## 2026-09-21 — The K02 row-shape consolidation was done here, not deferred further

The last open item from the K02 Fable review (its S4). Deferred out of the fix commit because a
refactor touching every unit does not belong beside a numerics fix, and done first on this branch
rather than left to rot, because the defect the review found had hidden behind exactly that
duplication.

Proved inert rather than assumed inert: a snapshot of every float row value, every compiled
residual, every CSC Jacobian entry, every state digest and both identity hashes, over five
variants at four states each, byte-identical before and after. Floats compared as hex.

**Two coverage gaps fell out of it, neither visible to any existing test.** Negating a lifting
definition row is invisible at a solution, where it is zero either way round. And **every
registered SYN-001 case declares a zero pressure drop**, so the sign of the `dP` term in
`P_out - P_in + dP` had never been exercised at all — flipping it passed the whole suite. Both
are covered now, the second at a 20 kPa drop the fixture never uses.

Writing the shared `energy_row` also exposed a bug I had just introduced in it — the source
branch double-counted the inflow — caught by a three-line arithmetic check before it reached any
unit. The accumulation order inside it is fixed and documented, because floating-point addition
does not associate and the consolidation was supposed to be inert.

## 2026-09-21 — The specification is commissioned before anything is implemented

Plan §4.2's *Model* column for K03 is **Fable / Opus**, and CLAUDE.md puts "scaling and
globalization policy" and "phase-attempt controller design" in Fable's lane. Four decisions here
have no test that would catch a bad choice until much later: the scaling construction, the
globalization rule, the phase-attempt contract, and what to do about a structurally
rank-deficient system.

So nothing is implemented until the specification lands. The brief is
`docs/briefs/K03-solver-specification.md`, written to a file first so the question is visible and
amendable rather than embedded in an agent call.

**The question that matters most** is which residual the Newton runs on. Plan §4.2's package
constraint says "the assembled sparse Jacobian of the reduced tear residual from the selected
backend", and three readings are open: reduce the 47-variable EO system to the three tear
variables by block elimination; solve the EO system whole with the tear as a structural label
only; or keep K02's procedural traversal and obtain `dR/dt` another way. My own reading is stated
in the brief so Fable can correct it rather than guess at it.

## 2026-09-21 — Q1 reversed by Frank: the r·F initializer is retired

His call, recorded as **R-014** superseding R-013. What I told him, and stand by: replacing does
*not* simplify the implementation, because blueprint §7.4's checked candidate chain is
architectural and exists either way; what it removes is the only registered coverage of the
rejection path. His instinct was nonetheless right that a registered initializer known not to
work is a wart that costs every future reader a paragraph. The synthesis Fable applied gets both:
derivation §9 registers `G(0)` and retires `r F_i` in two sentences, and the refusal becomes its
own registered case, `SYN-001-inadmissible-guess`, whose name says what it is for.

`Syn001Flowsheet.initial_recycle()` returns `G(0)` and matches §9's registered values at all five
variants, every one of which traverses. `retired_guess()` keeps `r F_i` as a named constructor
because a registered case still needs it.

## 2026-09-21 — A gate failure I shipped

Commit `6f68d74` left `compile/spec.py` failing `ruff format --check`. I had verified it with
pytest in an isolated worktree and reported "1023 tests green" — true, and not the gate, which is
ruff, ruff format, mypy and pytest. The specification agent caught it. **The lesson is not "run
the gate", which I know; it is that verifying in an isolated worktree tempted me to run a
*subset* and then report as though I had run the whole.** An isolated check must run
`./scripts/check.sh`, not `pytest`.

## 2026-09-21 — M1 and M2 measured

`numerics/scaling.py` and `numerics/linear.py`. Gate green at **1047 tests** (1024 before).
Mutation sweep: **22 of 22 caught** (one survivor first time round was a malformed mutation of
mine — `[] or sorted([]) or sorted(...)` short-circuits to the real call — not a test gap).

**Everything ADR 0004 and specification §4 assert was re-measured here rather than quoted**, and
all of it holds:

| Claim | Source | Measured independently |
| --- | --- | --- |
| `nnz(L) = 111`, `nnz(U) = 160` on the 44 × 44 block | ADR 0004 D1.2 | exactly reproduced |
| worst `ρ_lin` ≈ 1.3e-16 | ADR 0004 D3.2 | 1.19e-16 worst over five variants |
| `min\|U_ii\|/max\|U_ii\| ≥ 7.1e-3`, worst at r = 0.95 | ADR 0004 D3.4 | **7.129e-3 at r = 0.95**, exactly |
| unscaled κ ≈ 1e10–1e11 versus a few hundred scaled | spec §4.3 | 1.07e11 → 337 at nominal |
| `IterRefine="NO"` rejected, `"NOREFINE"` accepted | ADR 0004 D1.1 | holds on SciPy 1.15.3 |
| `Equil` inert on the `splu` path | ADR 0004 D1.3 | bit-identical `L`, `U` and solution |

**Two bugs of my own, both caught by a test rather than by reading:**

1. `np.min(values, initial=0.0)` takes the minimum *with* zero, so `min |U_ii|` was reported as
   0.0 for every positive diagonal — turning ADR 0004 D3.4's pivot screen into a constant that
   would have flagged every solve as suspect. Found because the measured ratio disagreed with
   the ADR's 7.1e-3.
2. A test of mine asserted the scaled state round-trips *exactly*, reasoning that the nominals
   are powers of ten times small integers. Exactness in binary needs powers of **two**. The claim
   was simply false; the test now asserts one rounding, and asserts that it is *not* exact, so
   the comment cannot rot into a lie if the scales ever change.

## 2026-09-21 — M3 measured

The damped Newton and its bounded line search (`numerics/newton.py`), with the recorded metadata
it emits (`orchestrator/trace.py`: `SolvePolicy`, `SolveEvent`, `Checkpoint`, `Trace`). The layer
split is the blueprint's: numerics computes and emits, the orchestrator records and decides.

Gate green at **1066 tests** (1047 before). Mutation sweep: **25 of 25 caught**, after five
survivors exposed five rules with no state that made them bite. Every one is now registered:

1. **Convergence tested on the *scaled* residual survived.** Every seed either used a unit scale
   or converged regardless. The discriminating state is a residual of 6e-8 with a row scale of 3
   against the registered 3.1e-8: unscaled it is not converged, scaled it is. Blueprint §7.3
   keeps verification tolerances independent of scaling exactly so that choosing a scale cannot
   change whether an answer is accepted.
2. **`any` over rows instead of `all` survived** — no seed had one converged row beside an
   unconverged one.
3. **Arithmetic bound landing instead of exact survived.** BND-01's landing happens to be exactly
   0.0 by arithmetic too. Found by search: from `x = 3.8139552653167543` along
   `d = −6.403089514483589`, `x + α_max d` is **−4.440892098500626e-16** — the magnitude §5.3
   itself names. ADR 0001 D3.1 makes exact zero the difference between a dormant stream and a
   flowing one, so that landing is a *negative flow* in a model that treats zero as special.
4. **A phase change going undetected survived** — no seed had a signature at all.
5. **An `error` being swallowed as a rejected trial survived** — no seed returned `error`.

**A prediction of the specification confirmed by accident.** The phase-rejection test ends in
`STAGNATION` at 1.4999967 with the residual still 2.5: the step halves until it lands just short
of the frozen regime's wall, is accepted, and the next step does the same, so the solver *crawls*
toward the wall. That is precisely what §9.3 describes and why `phase_wall_patience` exists — an
attempt that keeps rejecting phase-changing trials is grinding against a wall it should stop at.
The controller that acts on it is M5's; M3 asserts only that the solve never silently crosses.

Two errors of mine in the seeds, both caught by the first run:

- I passed the *state* where the merit wants the *residual*, so A31's `1/24` failed. The
  specification's number is right; my transcription was not.
- I asserted NUM-02 at r = 0.95 converges to exactly `20.0`. It converges to
  `19.999999999999982` — and so does `f/(1 − r)` evaluated in doubles, because `1 − 0.95` is
  `0.050000000000000044`. The solver agrees with the closed form **exactly**; demanding 20 would
  demand it be more accurate than the thing checking it. The test now asserts both: bit equality
  with the double-precision closed form, and the registered tolerance against the analytic 20.

## 2026-09-21 — M4 measured: the tear solves

`orchestrator/rank.py` (structural alias elimination) and `orchestrator/tear.py` (the tear
problem, the Schur complement and the consistency check). Gate green at **1103 tests** (1067
before). Mutation sweep: **19 of 19 caught**, after six survivors exposed six rules with no
state to bite them.

**The flowsheet is solved.** From the registered initializer, at every registered variant:

| Variant | outcome | iterations | `\|t − t*\|` | factorizations |
| --- | --- | --- | --- | --- |
| nominal | CONVERGED | 1 | 4.4e-16 | 1 |
| once-through | CONVERGED | 0 | 0 | 0 |
| high-recycle | CONVERGED | 1 | 3.9e-14 | 1 |
| all-liquid 310 K | CONVERGED | 1 | 0 | 1 |
| all-vapor 420 K | CONVERGED | 0 | 0 | 0 |

One step each, or none — exactly what derivation §9's affine-ray argument predicts, and exactly
why it warns that these variants exercise the derivative and the convergence test but *not* the
globalization. The off-ray start OFF-A takes more than one step and is tested separately.

**The derivative is checked three ways that share no route.** Against Fable's 40-digit closed
form: **2.8e-16** at `t*`, **1.6e-15** at OFF-A, against a registered 1e-12. Against a central
finite difference of the traversal: **3.3e-11**, which is that oracle's own floor. And against
the affine-ray identity `J(t*) t* = −(1 − r) t*`, differentiated from K02's metamorphic
relation: **1.9e-16**. Inner consistency `η` is **9.9e-17** at `t*` against a 1e-10 bound.

**The finite difference is unusable at `t*`, measured.** The central stencil leaves the mixer's
domain on two of three columns, because `t*` *is* the saturated boundary. That is why plan §4.2
demotes it to an oracle, and the implementation raises rather than returning a one-sided
difference wearing a central difference's error bound.

**The elimination was derived independently of the specification's table** and reached the same
two rows with the same signs — a third confirmation of the correction I made to those signs, now
from a graph traversal rather than from linear algebra or from the conflict state.

### The six rules that needed a state to bite them

1. **and 2. Leaving the derivative in scaled units, and transposing the two scales.** For
   SYN-001 `S_ρ = S_t = 3`, so the transformation is the identity and *any* handling gives the
   same numbers — §3.4 says so in advance. Now checked on a doctored scaling where it is a
   factor of 3.
3. **Skipping the consistency check inside `jacobian`.** A test calling the method proves the
   method works. Now an injected wrong reconstruction makes `jacobian` itself refuse.
4. **Loosening `η_inner` a millionfold.** Every honest state passes either bound. The
   discriminating state is a 1e-5 K nudge, whose scaled inner residual lands between them.
5. **Pinning a phase signature into the lifted context.** Numerically inert — the lifted
   function has no phase switch, which is exactly what the bit-identity test establishes — so no
   measurement can catch it. Asserted as a contract instead: a context pinning a regime claims
   the function depends on one, and [A01] would then mean something else.
6. **Skipping the linearity witness in the elimination.** The synthetic graphs are affine by
   construction, so nothing there could catch it; residuals with a moving mismatch are supplied
   directly.

## 2026-09-21 — M5 measured, and **G00 closes**

`orchestrator/attempts.py`: the bounded attempt controller, the frozen phase set, the phase-wall
restart and cycle detection. Gate green at **1130 tests** (1104 before). Mutation sweep:
**13 of 13 caught**, after six survivors of which four were real gaps and two were provably
inert (recorded as such rather than forced).

### Gate G00 is closed

"Three-component ideal process with all named v0.0 units and one numerical tear." From the
registered initializer, to Fable's 20-digit recycle, at every registered variant:

| Variant | attempts | iterations | `\|t − t*\|` |
| --- | --- | --- | --- |
| nominal | 1 | 1 | 4.4e-16 |
| once-through | 1 | 0 | 0 |
| high-recycle | 1 | 1 | 3.9e-14 |
| all-liquid 310 K | 1 | 1 | 0 |
| all-vapor 420 K | 1 | 0 | 0 |
| OFF-A (off the ray) | 1 | 2 | 2.2e-16 |
| **OFF-B** r = 0.5 | **2** | 2 + 2 | 3.3e-16 |
| **OFF-B** r = 0.95 | **2** | 2 + 2 | 1.2e-14 |

The solved flowsheet also reproduces the registered vapour product, purge and both duties, and
closes the overall component balance and the energy identity — things no single unit can do.

**OFF-B matches §13.3 number for number**, including the per-attempt iteration counts that
Fable's prototype *measured* (2 and 2) rather than the bounds it registered (≤ 3 and ≤ 4). The
bounds alone cannot see the rule they exist for: a patience of 1 closes attempt 1 at iteration 1
and still satisfies "≤ 3". The measured values are pinned.

### A bug the specification's own reasoning predicted

My first controller reported a seven-stream signature where §9.1 defines the attempt signature
as the flash map alone. Every variant then restarted two or three times and the *same* signature
appeared twice in a solve, which §9.4 forbids. That is exactly the cost §9.1 predicts for
freezing more than the residual depends on, and M3 had already observed the shape of it on a
synthetic problem: the solver crawls to a wall it need not cross.

### The wall needed the core's own numbers

My first wall inferred iteration indices and step lengths from outside the Newton core, which is
guessing — OFF-B ground through **11** iterations where the rule closes the attempt after 2. The
core now takes an `IterationObserver`: it reports a rejected trial with the real iteration, step
length and signature, and asks after each iteration whether to close. The core stays generic
(it knows a registered rejection reason, not what a phase is); the policy stays the
controller's.

### The four real gaps, and the two inert mutations

Real: cycle detection removed, the attempt budget unbounded, `phase_wall_patience` reduced to 1,
and an armijo rejection counted as a phase wall. All four needed a *constructed* two-regime
problem, because no registered SYN-001 case cycles, exhausts its attempts, or damps at a wall.

Unbounded attempts surfaced a defect of mine worth recording: on exhaustion the result reported
`policy.max_attempts` rather than the number of attempts actually run. The two coincide when the
loop is bounded by the cap — which is precisely why reporting the cap looked right and hid a
loop that was not bounded by it.

Inert, and recorded rather than forced:

- **"a converged attempt still restarts"** — without the early return the fallthrough reaches
  `_restart_point`, which returns `None` for a converged outcome, and `_closed` is then called
  with the same arguments. The early return is a readability choice. The rule is still tested.
- **"restart from the first rather than the largest α"** — the line search tries
  `α_max, α_max/2, …` in strictly decreasing order, so the first phase-rejected trial in a line
  search *is* the largest-α one. §9.4's "largest α, first encountered on ties" is one rule
  written twice for this search order, and no mutation between the halves can change a result.
