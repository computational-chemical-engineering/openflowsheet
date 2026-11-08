# ADR 0073 — WIT: the derivative witness escalates a failing small-flow column, and treats a γ–φ-IG split's dormant sides by whether a derivative exists

**Status:** **Proposed, 2026-11-08.**
- It takes effect on `main` when four things hold:
  - the build lane has implemented K04 §4.8.1–§4.8.9, assertions WIT.A01–WIT.A14 pass, and the moves M-1 to M-3 are
    amended (§4.8.6);
  - F0 `scripts/corpus_identity.py --check` is PASS at the implementing commit (WIT.A13);
  - `scripts/gate.sh` and CI on both architectures have passed on the merge candidate;
  - the design-lane `reviewer` pass on the implementation is done.
- Until then the witness is K04 §4.8 with R-281 and R-831, unchanged.
- Register entries are added on acceptance (drafts below, unnumbered).

**Author:** design lane (`specifier`). **Brief:** `docs/briefs/WIT-specifier.md`.
**Normative detail:** `docs/derivations/K04-certificate-spec.md` §4.8.1–§4.8.9; § numbers below refer to it.
**Reference values:** `docs/derivations/scripts/wit_reference.py` → `wit_reference.json` (`--check`).

**Amends:**
- **K04 §4.8.** The sentence quoted in §4.8.1 is replaced. The tolerance, the step and the two checks are not.
- **ADR 0013 Amendment 3 item 7 (R-281; R-345).** Its record (`derivative_witness_partial`, no qualification) also
  covers class 2: a dormant liquid side on a γ–φ-IG basis. R-281's own set is unchanged.
- **S11 rulings item 2 (R-831).** Z gains class 4: a dormant vapour side on a γ–φ-IG basis. The positive-sibling
  condition stays everywhere else.

**Closes:** X10 review M-1's follow-up (L-X10-1), and S11 rulings OQ-5 ("recorded, not widened").
**Answers:** OPT D-42's question to the design lane.
**Does not amend:**
- `FD_RELATIVE_STEP` and `DERIVATIVE_TOLERANCE`;
- the check policy document and `check_policy_sha256`;
- any frozen field set or schema;
- the regularity screen;
- ADR 0001 D2 and ADR 0007.

**Affected requirements:**
- A08: the evidence of derivative accuracy for the final unregularized Jacobian;
- D14: a certificate is model verification;
- blueprint §8.1 (the certificate) and §13.1 (the verifier is tested adversarially).

**Affected packages:**
- K04's verifier (`verify/checks.py`, `verify/certificate.py`);
- tests in S11 (GP-C3) and M02 (G7(c));
- the X10 inventory and T08's support envelope;
- OPT, downstream, after acceptance.

## Context

The witness differences each column centrally at `h_j = 1e-5 S_x,j` and compares the result with the AD Jacobian at
`τ_D = 1e-7` (scaled). Two registered situations defeat that stencil, while the Jacobian itself is correct.

- **L-X10-1.** `c1.reactor_surrogate` on `benchmarks/m04/c1-surrogate.json` carries per-tube flows of 1.4e-4 to
  4.9e-3 mol/s against `S_x = 3` mol/s.
  - The scaled entries of `R:C1RX-temperature` reach 1.36e3. `τ_D` is then a relative demand of about 1e-10.
  - The central difference's O(h²) truncation is 0.109, falling exactly 4× per halving. The AD Jacobian is consistent.
  - The truncation is not set by the flow. `S1.n.N2` sits 59 steps from zero and still fails at 0.105.
- **OPT D-42.** On `wilson-ig-v2`, a held single-phase split has one side exactly zero. The central backward point is a
  negative flow, refused under ADR 0001 D2, so the witness is `unsupported` and the certificate `UNVERIFIED`. The two
  sides are not alike:
  - **the vapour side** is affine in its flows on γ–φ-IG (vapour `ln φ ≡ 0`, an ideal-gas `h`). A one-sided
    difference there is exact: at GP-C3 345 K the AD entry and the forward five-point difference are both 0.5, bitwise;
  - **the liquid side** has no derivative at zero. `K_i(x)` is homogeneous of degree 0 in `l`, and the AD entry is the
    K-block's probe convention. At GP-C3 385 K the one-sided difference differs from it by 0.075, 0.26 and 0.39
    (scaled), independently of the step. These match closed forms from the record file to 4.6e-15 (§4.8.5).

The 2026-11-08 roadmap decision queued this item on the premise that any witness change moves registered certificate
bytes. The premise is false for a rule that is gated on the registered result (§4.8.6; K04 finding 9).

## Decision

**D1 — Escalation (class 5).**
- A component column with `x_j > 0` whose registered central result is refused or fails is re-differenced. The
  stencil is central fourth order at `h_k = h_j 2^−k`, for `k = 0…8`.
- Levels where a stencil point is refused are skipped.
- The column is resolved at the first `k` where two consecutive admissible estimates agree within
  `ε_res = τ_D/10 = 1e-8` over every row. The resolved estimate replaces the registered one in both checks, against
  `τ_D`.
- An unresolved column keeps its registered result exactly.
- The selection reads the residual only, never the Jacobian.
- Measured:
  - the surrogate resolves on all six failing columns (`k* ≤ 5`, escalated discrepancies `≤ 4.3e-10`) and certifies
    `VERIFIED`;
  - ADV-06 M's noise never resolves (smallest `e_k` = 30 `ε_res`), and its certificate is unchanged.

**D2 — The dormant vapour side (class 4).** On a γ–φ-IG basis, the columns of a lifted split's vapour side are
differenced by R-831's forward five-point stencil when every one of them is exactly zero. No record is written. The
justification is §4.8.4's affinity argument.

**D3 — The dormant liquid side (class 2).** On a γ–φ-IG basis, the columns of a lifted split's liquid side are not
differenced when every one of them is exactly zero. The `derivative_witness_partial` limitation lists them, in
R-281's record and R-345's form. No derivative exists there (§4.8.5).

**D4 — Identity.**
- A column whose registered result passes is untouched.
- Classes 2 and 4 occur only where today's witness is `unsupported`.
- So every certificate whose witness passes today is byte-identical. That includes every F0 certificate: 57
  `CONVERGED`, all `VERIFIED`.
- The intended moves are §4.8.6's M-1 to M-5, and none is registered in F0.
- No question to Frank is needed for identity.

**D5 — No new record.** No field, limitation kind, reason or policy entry is added, so the frozen field sets and the
policy hash hold. The escalated columns can be recomputed from `x_final`. R-831's Z writes nothing either.

## Alternatives considered

- **A step relative to the state, `h_j = ε max(|x_j|, floor)` (the brief's option 1; X10 M-1's suggestion).**
  Rejected for three reasons. It changes the stencil a priori, so it moves every certificate whose columns it touches.
  It does not fix L-X10-1: `S1.n.N2` fails at `x/h = 59` because the surrogate's curvature scale is its input box. And
  it trades truncation for roundoff on rows with large terms.
- **A smaller registered step, or a larger tolerance.** Rejected. R-831 already rejected both: the first moves every
  certificate, and the second is a relaxed check.
- **The central second-order stencil at halved steps.** Rejected. On `S1.n.N2` it reaches 2.2e-9 at one step and
  5.6e-8 one halving later, so its successive estimates never agree within `ε_res` robustly.
- **The forward five-point stencil for the escalation.** Rejected. Its roundoff constant is 128/12 against 18/12 for
  the central one, so it is noisier at equal step. It stays where only it is admissible (Z, class 4).
- **Reporting a Richardson-extrapolated value (sixth order) rather than `D_k*`.** Rejected. The bound `e_k*` would no
  longer apply to the reported number, and the measured escalated error (`τ_D/230`) needs no improvement.
- **Extending Z to every dormant phase on any basis (the brief's option 3).** Rejected for two reasons. On `pr-c1-v1`
  the forward points are refused and the dormancy convention is B17's (R-281). On γ–φ-IG the liquid side is not
  differentiable (D3).
- **Entry-level exclusion on the dormant liquid side**, which would difference those columns but skip the equilibrium
  rows. Rejected. It needs a new record granularity on a frozen limitation format, and it would witness only constant
  entries that the unit's two-phase states already witness.
- **Keeping held γ–φ splits `unsupported`, or declaring small-flow revisions `UNVERIFIED`.** Rejected. Either leaves a
  correct, differentiable Jacobian uncertified because of a limitation of the estimator. The first also treats
  γ–φ-IG worse than R-281 treats `pr-c1-v1`.

## Consequences

- **Code (build lane).**
  - `derivative_witness` gains the declared components and an escalation helper that receives no Jacobian (WIT.A07).
  - `verify_revision` builds classes 2 and 4 from its `lifted_splits` reading, and passes class 2 into the
    `unstenciled` set it already records.
- **Tests and records.**
  - M-1 (`test_oq5_…`) and M-2 (`test_g7c_at_delta_1e_4_…`) are amended to WIT.A10 and WIT.A09.
  - `scripts/x10_inventory.py --record` is re-run, and T08's L-X10-1 row and harvest note are closed (M-3).
  - New tests cover WIT.A01–WIT.A14.
- **Cost.** Escalation runs only on a column that already fails, at most 36 residual evaluations per column. ADV-06 H
  and M pay it; no `VERIFIED` certificate does.
- **OPT.** After acceptance, D-42 and D-82 (a) can be lifted for γ–φ held splits. G24 (c) can use a certified start
  rather than a relabelled one. That is OPT's own follow-up (M-4).
- **The one value judgment** is Q-WIT-1: whether a γ–φ vapour single-phase split should certify with a declared
  partial witness. The default is yes. It is R-281's precedent and Frank's "admit with declared limits" direction
  (R-924), and it is reversible by one class-table row with no registered move.

## Acceptance evidence

- WIT.A01–WIT.A14 pass on x86-64 and aarch64. The bitwise values of A10 and A14 are judged on the reference platform
  only.
- F0 `--check` is PASS (M1–M9) at the implementing commit. `scripts/gate.sh` passes, and CI passes on both
  architectures.
- `python3 -I docs/derivations/scripts/wit_reference.py --check` passes (49 claims).
- The `reviewer` pass covers the implementation against K04 §4.8.1–§4.8.9, in particular §4.8.3 (e) independence and
  §4.8.6's move list (rule 6: any further move is a defect of the specification).
- The manifest is `evidence/WIT/<commit>/manifest.json`, with `status: tested` before the merge. `reviewed` is never
  set by the build lane.

## Register entries (drafts, unnumbered)

**R-??? — WIT: a failing small-flow component column is re-differenced by an AD-independent escalation; an unresolved
one keeps its registered result.**
- *Decision.* Trigger: a component column with `x_j > 0` whose registered central result is refused or fails. Method:
  central fourth order at `h_j 2^−k`, `k ≤ 8`, refused levels skipped, resolved at the first consecutive pair that
  agrees within `τ_D/10` over every row. The resolved estimate replaces the registered one in both checks. No record.
- *Rejected.* A state-relative step; a smaller registered step; a larger tolerance; second-order central at halved
  steps; forward five-point; a Richardson-extrapolated report.
- *Evidence.* K04 §4.8.3, §4.8.6; L-X10-1 resolves (`k* ≤ 5`, `≤ 4.3e-10`); ADV-06 M is unchanged.
- *Watch for.* The escalation reading the Jacobian; a passing column escalated; any F0 move; a non-component column
  escalated.

**R-??? — WIT: on γ–φ-IG, a lifted split's dormant vapour side is differenced one-sided (R-831's stencil); the
positive-sibling condition stays everywhere else.**
- *Decision.* As D2.
- *Rejected.* Dropping the positive-sibling condition generally (it guards conventions on liquid sides and on
  `pr-c1-v1`).
- *Evidence.* §4.8.4; G1 = 0.5, reproduced bitwise; the class-4 part is 2.39e-11.
- *Watch for.* The rule applied to a liquid side, to a non-γ–φ-IG basis, or to a stream that is not a split side.

**R-??? — WIT: on γ–φ-IG, a lifted split's dormant liquid side is not differenced and is listed in
`derivative_witness_partial` (R-281's record).**
- *Decision.* As D3.
- *Rejected.* An entry-level exclusion; keeping such states `unsupported`.
- *Evidence.* §4.8.5's G2 gaps (0.075, 0.26, 0.39 scaled), matched to 4.6e-15 relative.
- *Watch for.* The exclusion widened to a vapour side, to a side with a positive column, or to another basis without
  its own non-differentiability evidence.
