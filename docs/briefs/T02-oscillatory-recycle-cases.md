# T02 — required oscillatory and hard recycle cases

**Status:** required inclusion in T02's registered cases, at Frank's request (2026-09-24): *"Please
define test cases that have the oscillatory behavior you need for the testing and include
these."* Addendum to `docs/briefs/T02-recycle-and-eo.md` §1 question 4.
**Authority for registration:** `fable-specifier` registers these in
`docs/derivations/T02-recycle-spec.md` and `benchmarks/t02/reference_values.yaml`. It may add
cases, and may change a parameter with a stated reason, but may not drop one of these five.

## Why these are needed

SYN-001 cannot test a recycle accelerator (brief §3.1–§3.2, measured). Where its loop is live,
`ρ(∂G/∂t) = r` exactly and the spectrum is real and non-negative, so it never oscillates. K03's
Newton converges in one step because the map is linear along the ray on which its initializer
starts. The cases below each break one of those comforts.

## Construction: manufactured fixed point, designed Jacobian

For three components with scale `S = 3 mol/s`:

    G(t) = t* + A (t − t*) + γ · q(t − t*) / S,     q(d) = (d₂d₃, d₃d₁, d₁d₂),     t* = (1, 2, 3) mol/s

By construction, **`t*` is the fixed point exactly**, **`∂G/∂t(t*) = A` exactly** (q is quadratic
and vanishes with its gradient at `t*`), and `γ` sets how nonlinear the map is away from `t*`
(`γ = 0.1` below unless stated). Nothing depends on thermodynamics. These are manufactured
solutions of the same class as K03's `NUM-02-linear-recycle`, **not physical flowsheets** (see the
last section).

Component flows must stay non-negative (ADR 0001 D3), so an iterate with a negative component is
an **invalid state**, and the case has to be handled by the solver's invalid-state rule, not by
clipping.

## The five cases

| Case | A | start `t0` | Spectrum | What it tests |
| --- | --- | --- | --- | --- |
| **REC-01 oscillating** | `diag(−0.90, 0.50, 0.20)` | `0.5 t*` | real, dominant **negative** | Plain substitution converges but the error alternates in sign every iteration; damping helps |
| **REC-02 divergent oscillation** | `diag(−1.50, 0.50, 0.20)` | `0.5 t*` | `ρ = 1.5` | Plain substitution diverges, and its **second iterate has a negative flow** (invalid state); damping or Anderson must recover |
| **REC-03 mixed sign** | `diag(0.95, −0.95, 0.30)` | `0.5 t*` | `±0.95` | **No damping factor helps** (best ω = 1, rate 0.95); only acceleration does. The case that proves Anderson is needed and damping is not enough |
| **REC-04 spiral** | `0.95·R(120°) ⊕ 0.30`, R a planar rotation | `0.5 t*` | complex pair `0.95 e^{±2πi/3}` and 0.30 | Rotational, not alternating, oscillation — a sign-alternation detector does not see it |
| **REC-05 non-normal** | `[[0.5, 2.5, 0], [0, 0.5, 2.5], [0, 0, 0.5]]` | `1.1 t*` | all 0.5, `‖A‖₂ = 2.80` | **Locally contractive yet globally divergent.** The linear error grows to 8.70× (iteration 3) before decaying; with the quadratic tail, plain substitution diverges from 10 % away. A contraction estimate from the spectrum is wrong here, and a "residual increased → abort" safeguard misfires on the linear version |

`REC-05` is registered in two variants: `γ = 0` (transient growth, then convergence — the
safeguard must not abort) and `γ = 0.1` (substitution diverges despite `ρ = 0.5`).

## What is exact, and can be asserted as such

- The fixed point `t*` and the Jacobian `A` at it — by construction.
- The spectrum, and whether plain substitution is locally convergent (`ρ(A) < 1`).
- For a real spectrum, the best single damping factor and its rate, in closed form:
  `ω* = 2 / (2 − λ_min − λ_max)`, rate `(λ_max − λ_min) / (2 − λ_min − λ_max)`.
  REC-01: `ω* = 0.8333`, rate `0.5833`. REC-02: `ω* = 0.6667`, rate `0.6667`. REC-03: `ω* = 1`,
  rate `0.95` — damping cannot improve REC-03.
- REC-02's plain substitution produces a negative component at iteration 2 (`t_k − t* = A^k(t0 − t*)`
  in the linear part; the first component is `1 − 0.5·(−1.5)² = −0.125` at `k = 2`).
- REC-05's linear transient growth `‖A^k d₀‖/‖d₀‖` for `d₀ = 0.1 t*`:
  `1.00, 2.74, 6.76, 8.70, 8.27, 6.72, 4.97, 3.44, 2.28` for `k = 0…8`.
- For the linear variants (`γ = 0`), Anderson with depth `m ≥ 3`, no damping and exact arithmetic
  is equivalent to GMRES and terminates in at most 4 iterations. **Measured: exactly 4 on all
  five linear variants** with the prototype below. What floating-point allowance to register is
  Fable's call.

## What was measured, and is *not* a registered expectation

Measured on 2026-09-24 with a prototype, **unsafeguarded** Anderson (type II, depth 3, plain least
squares) and the closed-form best damping — to confirm the cases separate the algorithms, not as
targets for the implementation:

| Case | Plain substitution | Best damped | Anderson m = 3 |
| --- | --- | --- | --- |
| REC-01 | 219 (alternating every step) | 44 | 8 |
| REC-02 | **diverges**, negative flow at iteration 2 | 58 | 8 |
| REC-03 | 463 | **458** | 10 |
| REC-04 | 463 | 39 | 8 |
| REC-05 (γ = 0.1) | **diverges** | 13 | 11 — **to a different root** (see below) |

Iterations to a residual of `1e-10`, with `γ = 0.1`.

**Correction, 2026-09-24.** The Anderson entry for REC-05 originally read "11" as if it had
converged to `t*`. It had not: it reached a second genuine fixed point
`S1 = (3.8887…, 2.5769…, 3.1111…)` (residual 8e-16), 2.95 mol/s from `t*`. The prototype tested
the residual and never which root it had found. Fable's specification pass caught it (T02 spec
§15 finding 1), and it was confirmed independently here: every other entry in the table does reach
`t*`. `S1` is repelling under plain substitution (an eigenvalue of 1.168 there), so Anderson
converging to it is itself a finding. REC-05 with the tail is registered as the recycle
**multiple-root** case rather than dropped. The registered assertions for the real,
safeguarded solver are Fable's to write: inequalities (for example "converges", "fewer than
plain substitution", "detects oscillation", "restarts at least once") are falsifiable where an
exact iteration count is not.

## On physics — why these are synthetic

Real oscillating recycles exist, but not in SYN-001's unit set. Mixers, splitters, isothermal
flashes, and CSTR or PFR reactors with ordinary power-law kinetics give recycle maps whose outlet
rises with the inlet, and SYN-001's measured spectrum confirms it for this flowsheet. Oscillation
in practice comes from:

- **exothermic adiabatic reactors** — more reactant makes the reactor hotter, so conversion rises
  and less reactant comes back;
- **heat-integration loops** — feed–effluent exchangers;
- **specification feedback**.

Those need T05's units, a PH flash and a heat exchanger, and they are T06's to register:
NET-07, the thermally coupled recycle, is mandatory there. These five manufactured cases test the
*algorithm*; a physical oscillating flowsheet should follow when the units exist.
