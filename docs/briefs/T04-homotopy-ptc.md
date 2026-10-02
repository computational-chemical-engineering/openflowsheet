# Brief — T04 specification: typed adaptive homotopy and one qualified PTC family with safeguarded SER

**To:** `specifier` (design lane)
**From:** the session (build lane), 2026-09-24
**Branch:** `wp/T04`, from `main` at the T03 merge (`fc8e0ca` or later)
**Deliverable:** a specification, ADR 0010 (Proposed), reference values and a work order — §8.
Commit on `wp/T04`, staging named paths only; messages end with
`Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01QMQnXcFna3j5D6Ai9Ja9AE`.

## 1. The question

What exactly must T04's globalization do: one typed homotopy, one PTC family with the safeguarded
SER controller, and the third recovery edge (EO globalization failure → homotopy or qualified PTC).
For each, give the formulation, the policy constants, the records, the registered cases with
independent expected values, and numbered falsifiable assertions. Say whether the PTC family
qualifies, on which evidence, or register it as experimental and gate V14 as incomplete (plan
§4.3). The answer must be complete enough for the build lane to implement without deciding
anything scientific.

## 2. Why it needs the design lane

Everything in it is lane-rule design work (plan §1.3): new numerical algorithms, a mass-matrix
derivation, sign and mapping conventions, a step controller, qualification and basin-comparison
verdicts, and schema changes by ADR. A wrong mapping is silent. `−F` used as dynamics without
checking the sign or mapping (plan §4.3) converges to the same root on easy cases and to a
different root, or none, on hard ones. And a PTC that "works" on a case chosen after the fact is
not qualified.

## 3. Current state (verbatim where it binds)

**Plan §4.3, T04 row** (`docs/implementation-plan.md:242`). Acceptance: *"Endpoint equivalence;
λ<1 not target-verified; PTC derivation and basin comparison; accepted/rejected step controller
tests and budgets."* Requirements D01, D07, A03; gate **V14** *"Homotopy, qualified PTC/SER and
three bounded recovery edges."* Second-lane note, in full:

> PTC first family: implement a flash with liquid and vapor holdup (mass and energy accumulation)
> with explicit residual sign and mass mapping; it is the most defensible physical derivation for
> this codebase because SYN-001 already supplies its equilibrium, and SYN-001 at r = 0.95 is the
> registered basin comparison against damped Newton. Start with a small stable analytic limit, then
> the coupled process case, then an exothermic multiple-root reactor — the physically unstable
> branch of which is exactly the example blueprint §7.5 cites. Derive static equivalence. Do not
> use −F as artificial dynamics without checking the sign/mapping. Use the precise SER policy of
> v3.1 §7.5, record pseudo-time scale and limits, and verify the target residual. If no useful
> qualified family passes, retain PTC as experimental and record the v0.1 gate as incomplete; do not
> enable it solely because BTF found a large block.
>
> Recovery minimum: register three distinct edges: recycle acceleration restart/damping; stalled
> recycle → EO merge; EO globalization failure → typed homotopy or qualified PTC. Every edge has a
> direct injected failure, precondition, maximum count, and evidence that fixed
> physics/specifications did not change.

**Blueprint §7.4** (`docs/blueprint-v3.1.md:283-290`): *"Homotopy defines H(x, λ), an easy endpoint
and H(x,1) = F(x), including all original specifications. Examples include recycle closure,
reaction activation, heat coupling, and nonideality. Each transformation declares its path
domain, scales, and endpoint mapping. Adaptive steps retain rollback checkpoints. A checkpoint at
λ < 1 solves a modified problem and cannot receive a target-problem certificate. Failure to advance
is `HOMOTOPY_STALLED`; branch loss is a hypothesis unless supported by diagnostics.
Pseudo-arclength continuation for folds is deferred, with a multiple-root benchmark retained from
v0.1."*

**Blueprint §7.5 + [A03]** (`:291-322`): `M(x̂) dx̂/dτ = −F̂(x̂)`, linearized step
`(M_k/Δτ + Ĵ_k) Δx̂ = −F̂_k` (Kelley–Keyes 1998). It is not a converged implicit-Euler step and not
a DAE integrator. It requires a declared `M`, sign conventions, a time-scale policy, a domain and
consistent initialization. It is qualified by physical derivation *or* empirically against damped
Newton. Both routes need steady-state equivalence, dimensional and sign checks, algebraic
consistency and bounded domain handling. **SER:** with φ_k = ‖F̂_k‖₂ over accepted iterates at
fixed scales,
`Δτ_{k+1} = clip_[τ_min, τ_max][Δτ_k · clip_[γ_min, γ_max](φ_k / max(φ_{k+1}, φ_floor))]`.
- The initial pseudo-step, the limits, the residual floor and the growth and shrink limits (2 and
  0.2 suggested) are registered.
- On a rejected, domain-invalid or failed-linear-solve step: keep the previous state and residual,
  shrink the step by 0.5 and retry within a bound. Rejected trials never enter the ratio.
- Stop on the original verification criteria, before a near-zero residual inflates the ratio.
- Reset on a scale, mass-policy or active-set restart.
- Trace the proposed and accepted pseudo-steps and the rejection reasons.

PTC *"can favor some roots over others and does not prove dynamic stability"*.

**ADR 0008 D3.4 / D5 (Accepted)** fixes part of the mapping already:

> With D3.3, a holdup row's `F̂_row` is `−F_row` (an exact row sign of −1), and an algebraic row's
> `F̂_row` is `F_row`. T04 must declare this row-sign map explicitly in its PTC mapping, as one named
> constant applied to residual and Jacobian together … The magnitudes of `M` (holdup nominals,
> residence times, thermal inertia) and the equation-to-variable mapping remain T04's derivation
> under D07 … a row may receive a nonzero `M` entry only if its manifest kind is `holdup_balance`.
>
> Test: for the SYN-001 flowsheet, the set of rows with nonzero `M` equals the set of
> `holdup_balance` rows.

**SYN-001 today (measured on `main`):** 49 rows × 47 variables before the two structural
eliminations. Accumulation kinds: 37 `algebraic`, 4 `zero_holdup_balance` (`U-MIX:MIX-mole:A/B/C`,
`U-MIX:MIX-energy`) and 8 `holdup_balance`:
- `U-HEAT:HEAT-mole:A/B/C` and `U-HEAT:HEAT-duty`;
- `U-FLASH:FLASH-mole:A/B/C` (holdup `N_i`, component moles in the drum) and `U-FLASH:FLASH-duty`
  (holdup `U`, internal energy of the contents).

The flash's `FLASH-T` row pins the temperature in the nominal flowsheet. In the A02 revisions
(T02 §7.3) `S3.T` is freed and `U-FLASH.Q` is specified.

**Solver today.**
- K03's damped Newton (`numerics/newton.py`; K03 spec §5): Armijo `c = 1e-4`, 20 halvings,
  bound-aware exact landing, stagnation over a window of 5 at ratio 0.99, 50 iterations per
  attempt, 5 attempts, 10 000 property calls by default (`orchestrator/trace.py:355-370`; 20 000
  is SYN-001's registered capped-budget case, `budget.py:34`).
- T02's Anderson recycle with the stalled-recycle → EO merge. Edges 1 and 2 of the recovery minimum
  exist and are tested in T02; edge 3 does not exist.
- T03's phase-attempt contract (ADR 0005, **Accepted**): one `phase_contract.decide`, a frozen
  signature per attempt, the admissibility screen, adjacent restart, `BOUND_BLOCKED`
  disappearance, six opening checks, per-attempt contexts, and `branch_provenance` whose
  `opening_source` has no continuation value yet. T03 §8.1: *"Continuation history does not exist
  in v0.1 … T04 adds it by its own ADR."*

**Outcomes and schemas.** `SolveOutcome` (`orchestrator/trace.py:26`) has **no**
`HOMOTOPY_STALLED`, and nothing under `src/` or `schemas/` mentions homotopy or PTC. The only
mention is the failure taxonomy class `homotopy/PTC/active-set stalls` (`verify/failure.py:68`,
action `supply_initial_guess`). `SolvePolicy` has no PTC or homotopy fields. Every schema change is
an ADR (interfaces and schemas frozen at P01).

## 4. Measured facts — do not re-derive

- **PHS-05, handed to T04** (T03 spec §6.4, F1; `benchmarks/registry.yaml` `SYN-001-A02-355-dew-guess`,
  `handed_to: T04`). A02 revision, target 355 K (`Q_spec = Q_flash(355 K)`), guess 375 K. Bubble
  and dew points of `S3.n` at P_r are 351.444 169 091 K and 377.529 060 606 K.
  1. Attempt 1 (`TWO_PHASE`) lands `S3.vap.C` at α_max = 0.642 309 461 269 at 365.572 K, then ends
     `BOUND_BLOCKED` on it.
  2. Attempt 2 (`LIQUID`) opens 14 K inside the two-phase band (screen value 1.4345).
  3. All 21 of its trials are phase-rejected, and the solve ends `ACTIVE_SET_CYCLING`.

  Guess 377 K fails the same way. In T03's 75-run family scan (targets 340/355/358/360/365 K;
  guesses 300–430 K), only these two fail. Neither count-based nor merit-progress recurrence
  rescues it (T03 §7).

  T03's diagnosis: *"a Newton step from 375 K far larger than the region in which its
  linearization of the lifted split holds, which is a globalization question, not a phase-logic
  one."* T03 §13: *"The bound-driven disappearance premise holds at roots, not at Newton iterates
  far from them."*
- **SYN-001 r = 0.95** (`SYN-001-high-recycle`): the linear recycle `t = f/(1−r)` is 20 × f. The
  mixer's subcooling margin is 0.1004 at T_mix = 354.728 K. Derivation §9 proves the tear map
  affine along the ray through its fixed point, so Newton from the registered initializer lands in
  one step. The basin comparison therefore needs off-ray starts to mean anything.
- **REC-05** (T02/T03): a manufactured recycle with a second root `S1`, 0.963 scaled from `t*`
  (MR-A/B/C). It is the only registered multiple-root case, and it is not a physical model.
- **Carried from T03's review §7, or handed on:**
  - The tear path returns `attempts = 0, x = start` on a property-budget refusal (K03's registered
    capped-budget shape). The region path now keeps its attempts (review S1).
  - A converged solve without `x_final` would yield a schema-invalid certificate. This is a K04
    follow-up, **not** T04.

## 5. Already decided — not open

- The formulas and the SER policy of blueprint §7.4–§7.5 as quoted in §3, including "λ < 1 is never
  target-certified" and the rules for resetting and rejecting.
- ADR 0008 D3.4/D5: `M`'s pattern comes from `holdup_balance` manifests only, and the row-sign map is
  one named constant applied to residual and Jacobian together.
- The first PTC family is the flash with liquid and vapour holdup. SYN-001 at r = 0.95 is the
  registered basin comparison against damped Newton. The order is: analytic limit, then coupled
  process, then multiple-root reactor (plan §4.3).
- If no family qualifies, PTC stays experimental and V14 is recorded incomplete. PTC is never
  enabled because of a block's size.
- ADR 0005 is accepted and stands. Its frozen-signature rule ([A01]) binds every residual and
  Jacobian call, including pseudo-steps and homotopy steps. A globalization that changes the active
  set does so only through `phase_contract.decide`.
- Certificates are issued only for `CONVERGED` solves of the target problem (K04 §3; T03 review §8).
- R0 strings carry no measured float (T03 §4.10 as amended).
- `δ_root = 1e-4` and the root fingerprint (ADR 0005 D7) are reused, not redefined.

## 6. Genuinely open — what you decide

1. **Homotopy.** Which transformation is typed for v0.1 (recycle closure? heat coupling? another
   from §7.4's list?), on which case, and why. Decide `H(x, λ)`, its easy endpoint, path domain,
   scales and endpoint mapping. Decide the adaptive λ-step controller with rollback, and the exact
   `HOMOTOPY_STALLED` criterion.
2. **PTC mapping.**
   - The equation-to-variable mapping for the flash holdup rows, including the lifted split
     (T02/T03) and the energy row when `T` is specified versus when `Q` is.
   - The magnitudes of `M`: holdup nominals and thermal inertia, with units, derived and not tuned.
   - Consistent initialization and domain handling.
   - Whether the heater's holdup rows get `M` entries.
3. **SER constants.** τ₀, τ_min, τ_max, γ_min, γ_max, φ_floor, the retry bound, and the stopping
   rule relative to K03's convergence test.
4. **Composition with the phase-attempt contract.** Does a PTC or homotopy run live inside one
   attempt (frozen signature), or does each λ or τ segment open attempts? What does a phase wall
   mean during PTC? Which `decide` rows apply? What resets SER?
5. **Edge 3.** Which EO outcomes trigger it, its precondition, its maximum count, and its injected
   failure. The evidence must show that physics and specifications did not change.
6. **PHS-05's registration under T04.** Is it rescued (by which method, with registered numbers), or
   does it stay an expected failure (with the reason)?
7. **The multiple-root reactor.** Plan §4.3 names an exothermic multiple-root reactor as the third
   PTC case. There is no such unit model today; T05's list has a *conversion* reactor. Decide whether
   T04 registers a synthetic exothermic CSTR as a PTC case (its own derivation) or defers it, and what
   that does to qualification.
8. **Records and schemas (ADR 0010).**
   - `SolvePolicy` fields.
   - The outcome `HOMOTOPY_STALLED`.
   - Event kinds or fields for pseudo-steps and λ-steps, with their rejection reasons.
   - Continuation history on `branch_provenance` (a new `opening_source` value and item fields).
   - The failure taxonomy entries.
   - Which fields are R0 and which are floats under ADR 0007.
9. **The tear path's budget-refusal shape.** Fold it in (and re-register K03's capped case), or
   hand it on, with the reason.

Where a question turns on a preference only Frank holds (scope, a public name, compute), say so and
give a recommended default. Do not block on it (T03 §14's pattern).

## 7. How the answer will be verified

As in T03:
- An **independent twin** `docs/derivations/scripts/t04_reference.py`, in multi-precision, importing
  nothing from `process_runtime`/`benchmarks` (checked by AST).
- It emits `benchmarks/t04/reference_values.yaml` byte-identically on re-run, with `--check`
  self-checks. The YAML's SHA-256 goes in the spec header.
- Every registered number carries a margin argument showing it is decided far above the 53-bit floor
  (T03 §6.5's pattern).
- The build lane implements against numbered assertions `T04.A00…`. `scripts/t04_evidence_manifest.py`
  measures each one in process against the YAML. The cross-platform R0 half runs on the CI pair.
  `reviewer` reviews the implementation.
- Include ablations proving each rule load-bearing (T03 §6.7's pattern). At minimum: SER without the
  floor; rejected trials entering the ratio; no reset on restart; `M` on a non-holdup row, which must
  fail ADR 0008 D5's test.

## 8. Deliverable shape

1. `docs/derivations/T04-globalization-spec.md`: formulation, derivation of `M` and static
   equivalence, policy constants, records, registered cases, assertion catalogue (with the
   authority for each expected value), limitations (what is *not* established), open questions with
   defaults, and a **work order** (W0… for the build lane, with any measurement you need from the
   implementation *before* committing to a number flagged as W0, as T03 did).
2. `docs/derivations/scripts/t04_reference.py` and `benchmarks/t04/reference_values.yaml`.
3. `docs/adr/0010-…md` (Proposed; accepted when T04's manifest is `tested`), stating schema changes,
   affected requirements (D01, D07, A03, V14; D09/D11 where provenance changes), migration and
   acceptance evidence.
4. `docs/decision-register.md` entries (next free id after R-029) for every choice with a
   plausible rejected alternative.
5. Registry entries you want (build lane writes the YAML revisions), and PHS-05's re-registration if
   any.

## 9. Out of scope

- Pseudo-arclength continuation and fold following (blueprint §7.4: deferred).
- A general variable-step DAE adapter (§7.5: later work).
- Any T05 unit model other than what a registered PTC case strictly needs.
- The K04 certificate-without-state defect.
- Reopening ADR 0005's contract or the cycle rule. T03 §7 closed it on evidence.
- Performance at plant size.
- Human numerical and process-modelling sign-off.
