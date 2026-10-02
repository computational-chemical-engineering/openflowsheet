# Brief — T03 specification: the general procedural-phase active-set controller

**To:** `specifier` (design lane)
**From:** the session (build lane), 2026-09-24
**Branch:** `wp/T03` (from `main` at `128b54b`)
**Deliverables:** `docs/derivations/T03-phase-controller-spec.md` (numbered assertions), its reference
generator `docs/derivations/scripts/t03_reference.py` with `--check`, the emitted
`benchmarks/t03/reference_values.yaml`, and **ADR 0005** (`docs/adr/0005-phase-attempt-contract.md`,
pre-allocated by plan §4.1 for exactly this; register R-012).

## 1. The question

What is the general phase-attempt contract — the rule that decides, per attempt, which phase set is
frozen, how a phase appears or disappears, where the next attempt restarts from and with which
checkpoint, when a recurring signature is legitimate and when it is cycling, and what provenance a
returned root carries — stated as ADR 0005 and a test specification with registered cases, such that
the build lane can implement it without choosing anything?

## 2. Why it needs the design lane

Phase logic is on the plan's list of design-lane-led areas (plan §1.3, `CLAUDE.md` "The two lanes").
Every rule here decides which root a solve returns and whether a failure is honest; a wrong rule
passes every test written from it. Two such rules were already corrected by measurement (T02 §6.3.3:
the disappearance rule first fired only on a phase total; the nominal case leaves through a
*component*).

## 3. Current state (verbatim where it binds)

**Blueprint v3.1.**
- §6.3 [A01]: "the active phase set belongs to the **local nonlinear attempt**, not to individual
  residual calls. Freeze it for all accepted iterates, trial points, residual/Jacobian calls, and
  derivative perturbations within that attempt. The callback evaluates the declared fixed-regime
  equations; it must not silently run a globally stable flash that chooses another phase set."
  "A trial that cannot be evaluated in the fixed formulation returns a typed domain or
  `PHASE_UPDATE_REQUIRED` outcome. The orchestrator can reject the trial or terminate the attempt,
  restore a valid checkpoint, and ask the bounded outer active-set controller to select a new phase
  set and restart."
- §7.6 [A01]: "Outer active sets have change events, bounded retries, cycle detection, and
  deterministic tie-breaking. […] A solve returns one admissible root unless a root-search study was
  requested. Store branch provenance, starting point, continuation history, and a root fingerprint
  with comparison tolerances."
- §7.7: "Phase cycling → Bounded active-set restart or a validated alternative numerical
  formulation."
- Plan §4.3, T03 row: "general procedural-phase active-set controller and checkpoint
  compatibility" — acceptance: "No signature change during attempt; trial rejection/restart;
  sparsity rebuild; disappearing/reappearing phase; bounded cycling; multiple-root provenance."
  V15's gate row names "Frozen phases, EO cross-unit spec, multiple-root evidence."

**Interim contract 1 — the tear path, K03 spec §9 (normative until ADR 0005; register R-012).**
- §9.1 signature: the tuple of phase regimes of phase-selecting units the residual depends on; for
  SYN-001's tear `σ = (("U-FLASH", regime),)`; the heater outlet regime is not in it; dormancy is not
  a phase selection. (T01 derives `signature_units` structurally since T01.)
- §9.3: a trial with `σ' ≠ σ` is rejected `phase_update_required` and the step halved; the attempt
  ends `PHASE_UPDATE_REQUIRED` after `phase_wall_patience = 2` consecutive iterations with such a
  rejection, or when the line search fails / stagnation fires with one in the last
  `stagnation_window = 5` iterations. Restart point: the phase-rejected trial with the **largest α**
  in the last line search; caches kept, derivatives rebuilt.
- §9.4: "At most `max_attempts = 5` attempts per solve; exceeding it is **`ATTEMPTS_EXHAUSTED`**. A
  signature may be the signature of **at most one** attempt per solve; a restart into a signature
  already attempted is **`ACTIVE_SET_CYCLING`** (blueprint §7.6 cycle detection, the v0.0 rule; T03
  generalizes to signatures that legitimately recur). Ties: attempts are numbered in order; restart
  point by largest `α`, first encountered; signature equality is tuple equality in the fixed unit
  order."
- Code: `orchestrator/attempts.py` `solve_with_attempts` (the controller), `_PhaseWall` (the observer:
  rejections, `should_close`, best-α restart), `_restart_point`; one core per attempt — K03 Newton or
  T02's Anderson — under the same contract. Constants in `orchestrator/trace.py`:
  `REGISTERED_PHASE_WALL_PATIENCE = 2`, `REGISTERED_MAX_ATTEMPTS = 5`,
  `REGISTERED_ADMISSIBILITY_EPSILON = 1e-12`, `REGISTERED_STAGNATION_WINDOW = 5`.

**Interim contract 2 — the lifted EO path, T02 spec §6.3 (interim; "T03 generalizes").**
- An *active phase set* per lifted unit; inactive phase variables pinned at zero, their rows dropped
  (`region.py` `LiftedSplit.pinned/dropped`).
- §6.3.3 disappearance *during* an attempt: "A lifted variable of an active phase — its total (`V`
  or `L`) while the stream's total `N > 0`, *or* one of its components (`v_i` or `l_i`) while the
  stream's component `n_i > 0` — that reaches its bound — exact landing at `α_max` accepted as an
  iterate (K03 §5.3), or `α_max = 0` with the direction pointing outward — closes the attempt
  `PHASE_UPDATE_REQUIRED` with `reason: phase_disappeared(unit, phase, variable)`." (Since the T02
  review, S6: a `BOUND_BLOCKED` closure is attributed to the variable Newton reports as blocking,
  `NewtonResult.blocked_by`.)
- §6.3.4 appearance only *at closure*: (a) a converged root that fails K03 §8.2's admissibility
  check (`Σ x K ≤ 1 + ε`, `Σ y/K ≤ 1 + ε`, `ε = 1e-12`) restarts in the kernel's regime; (b) an
  attempt ending STAGNATION / LINE_SEARCH_FAILED / BOUND_BLOCKED / BUDGET_EXHAUSTED restarts in the
  kernel's regime at its end state if that differs (`kernel_disagrees(unit, regime)`).
- §6.3.6, verbatim: "**What T03 must add**, and the registered case that will judge it: *appearance
  detected during an attempt*, so that an attempt whose single-phase branch has no root in the
  provider domain does not have to fail before the phase can appear; and a *restart into the
  adjacent regime* when a step overshoots two regime boundaries at once (the largest-α
  phase-rejected trial of K03 §9.3 lands in the far regime). The registered cases
  `SYN-001-A02-360-liquid-guess` and `-355-liquid-guess` (§7.6) fail honestly under rules 1–5 and
  their expectations are T03's to re-register as successes."
- Region results carry per attempt: signature, outcome, Newton's own outcome, end state; a
  checkpoint (`candidate_root` only when the region kept the attempt, else `partial`); one
  `AttemptContext` per attempt with `active_phases` (ADR 0009 D4).

## 4. Measured facts you should not re-derive

- **The two liquid-guess A02 cases** (T02 A30/A31, measured 2026-09-24, closed forms in
  `benchmarks/t02/reference_values.yaml` `syn001.branch_roots`), both from heater guess 350 K:
  - `-355-liquid-guess` (`Q_flash = 24 681.106 068 625 242 W`): attempt 1 (heater LIQUID) *converges*
    to the all-liquid branch root `S3.T = 389.438 243 827 208 K`, rejected at closure,
    `Σ x K = 2.495 993 838 622 899`; attempt 2 opens VAPOR, whose vapour-branch root is at
    84.08 K (outside the provider domain 280–440 K); it runs to the 280 K edge; the kernel says
    LIQUID, already attempted → `ACTIVE_SET_CYCLING`. The true answer is 355 K, two-phase.
  - `-360-liquid-guess` (`Q_flash = 0`): attempt 1 LIQUID stagnates at 439.999 999 7 K (its branch
    root 442.64 K is outside the domain), kernel says VAPOR; attempt 2 VAPOR runs to
    280.000 02 K (branch root 137.28 K), kernel says LIQUID → `ACTIVE_SET_CYCLING`. True answer
    360 K, two-phase.
  - Bubble/dew points of `S3.n` at the reference pressure: 351.444 169 K / 377.529 061 K. Note that
    in both cases the solver never opens TWO_PHASE: the kernel's verdict at the domain edges is a
    single-phase regime, and a signature may not recur.
- **Multiple roots, registered.** REC-05 (γ = 0.1, manufactured recycle map) from `1.1 t*` reaches a
  second genuine fixed point `S1 = (3.8887…, 2.5769…, 3.1111…)`, not the designed `t* = (1, 2, 3)`;
  the T02 merge edge from the best iterate lands on `S1` too. Nothing today records which root a
  solve returned beyond the state itself.
- **Tear path under the v0.0 rule** is exercised by K03's registered off-ray cases (A06: LIQUID then
  TWO_PHASE, two attempts) and synthetic seeds in `tests/test_k03_attempts.py`.
- The checkpoint today: `Checkpoint` (`orchestrator/trace.py`) carries `signature`, `label`
  (`partial`/`candidate_root`), `verification_scope`, `state_sha256` (the solver's own variables),
  `full_state_sha256` (the 47-vector K04 verifies), `scale_segment`, `jacobian_identity` (unwritten),
  `step_index`. A restart today opens from the restart *point*, not from a stored checkpoint; there is
  no check that a checkpoint is compatible with the attempt restoring it (signature, scales,
  sparsity).

## 5. Already decided — not open

- ADR 0009 (accepted) is the plan/trace/schema baseline: `ExecutionPlan`, event kinds and fields,
  `AttemptContext.active_phases`, `Checkpoint.step_index`, outcomes `RECYCLE_STAGNATION`,
  `CAPABILITY_UNAVAILABLE`. Schemas change only by a design-lane ADR (ADR 0005 is that vehicle).
- A failed case stays failed; expected failures stay outside the success denominator until their
  re-registration as successes is itself specified and measured.
- Reproducibility: any float recorded from a least squares or a residual difference is registered
  with a comparability window, not a floor (ADR 0007 D2.2 as amended; register R-026).
- `PHYSICALLY_INFEASIBLE` stays outside the outcome vocabulary (blueprint §7.7).
- The region solve enforces the property budget (T02 review S4); the executor refuses to run a step
  whose problem differs from the planned one (M3).

**Genuinely open — what you decide:**
1. The general signature rule: when a signature may legitimately recur (K03 §9.4's "T03
   generalizes"), and what makes recurrence cycling — e.g. recurrence from a different checkpoint,
   a bounded count per signature, a change-event history.
2. Appearance during an attempt (T02 §6.3.6): the detection criterion on a trial or iterate (a
   kernel query? a stability test on the frozen-regime state? at what cost per trial?), and how it
   interacts with the frozen-phase rule of §6.3 [A01] — the callback may not choose a phase itself.
3. Restart into the adjacent regime on a double-boundary overshoot.
4. One contract for both paths (tear and lifted EO), or two with a stated relation.
5. Checkpoint compatibility: what a checkpoint must carry so that restoring it into an attempt is
   checkable (signature, scales/`scale_segment`, sparsity/`jacobian_identity`, `step_index`), and the
   typed refusal when it is not. "Sparsity rebuild" in the acceptance row: when the active set
   changes, what must be rebuilt and how that is evidenced.
6. Multiple-root provenance: the root fingerprint (what it hashes, its comparison tolerances under
   ADR 0007), branch provenance and continuation history per blueprint §7.6, where they are recorded
   (result, certificate, trace), and the registered multiple-root cases (REC-05's `S1` is available).
7. The two liquid-guess A02 cases: their re-registered expectations, with closed forms.
8. `role: free` without a value (T02 review N9): currently silently not freed; T02 §7.5 wants
   `INITIALIZATION_FAILED` naming the variable. Decide whether T03 owns it.

## 6. Already tried and rejected (evidence in the T02 documents)

- Disappearance only on a phase total (T02 §6.3.3 as first written): measured wrong — the nominal EO
  case leaves through `S3.vap.B` while `S3.V = 4.4e-5 mol/s`.
- No projection of the supplied split at `x⁰`: the forced all-liquid trivial root converges in one
  iteration to an inadmissible state (EO-TRIV, T02 A24).
- Attributing `BOUND_BLOCKED` to "the first watched variable at zero" (T02 review S6): replaced by
  Newton's `blocked_by`.

## 7. How the answer will be verified

The gate (`./scripts/check.sh`, 1539 tests on `main`) including K03's attempt tests and T02's region,
A02 and executor tests, which must stay green except where your spec deliberately re-registers an
expectation (name each). CI on x86-64 and aarch64 with the K05 identity comparison (any new R0 field
enters it). The evidence manifest `evidence/T03/<commit>/manifest.json` with one check per
assertion, generated by a script, as T01/T02 did.

## 8. Deliverable shape

As `docs/derivations/T02-recycle-spec.md`: authority and scope; what it establishes and **does not**;
the contract; registered cases with closed-form expectations and tolerances (with their floors); a
numbered assertion catalogue; the reference generator with `--check`; ADR 0005 (decision,
alternatives rejected, affected requirements, migration — including any schema change — and
acceptance evidence); open questions each labelled *needs a fact* or *needs Frank's preference* with
a recommended default; a FOR FRANK section only if something truly needs him.

## 9. Out of scope

Homotopy, PTC, SER (T04); new unit models or a general PH flash (T05); the reference corpus (T06);
jobs and bindings (T07); rewriting K03's Newton core or T02's Anderson core beyond what the contract
needs.
