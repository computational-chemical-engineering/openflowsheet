# Brief — T05b: remove the T05 PH/EO limitations (near-pure PH, single flowing component on EO, dormant PH-type outlet)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-25. **Branch:** `wp/T05b` (from `main`
after the T05 merge `1ba973b`).
**Deliverable:** the authority documents the build lane implements against — an ADR (0012 is the next
free number) amending what must be amended, a specification (recommended: a new
`docs/derivations/T05b-limitations-spec.md` with numbered assertions, registered states and
tolerances; T05's spec gets pointers, its §4.4/§4.7/§19 amended), reference values from an extension
of the twin `docs/derivations/scripts/t05_reference.py` (or a sibling) with `--check`, register
entries reversing R-049 and R-050 explicitly, and a work order. Write no production code; do not
commit (the build lane commits).

## 1. The question and the directive

Frank, 2026-09-25, answering T05 spec §19 Q11 and Q12: *"I want the software to have as little
limitations as possible. So, yes: the PH solver should be able handle near-pure feeds, and EO solves
can handle a single flowing component that is partly vaporised."* This reverses R-049 (no
conditioning criterion; the near-pure class a registered limitation, A29) and R-050 §4.7 (b)
(a single flowing component in the latent jump not solved on the EO path, A30). Under the same
directive the build lane put §4.7 (a) in scope — a dormant PH-type outlet on the EO path, which
converges at x⁰ and is certified only `UNVERIFIED` (A28) — because its remedy is the same ADR 0005
regime-lattice change. **Design, derive and specify how each of the three becomes a solved and
certifiable (`VERIFIED` where the state is regular) capability**, or, where a residual limitation is
unavoidable, prove it and state it minimally.

## 2. Why the design lane

It changes ADR 0005's regime lattice/decision function (phase-attempt contract), K04's independent
split and admissibility policy (certificate policy), and the PH kernel's numerics — all design-lane
subjects (CLAUDE.md "The two lanes"). If the controller's software design needs the `architect`, say
so in the deliverable, with the question for it; do not guess at code structure.

## 3. Current state (read; the facts are there, with measurements)

- T05 spec `docs/derivations/T05-unit-models-spec.md` **§4.2** (why the PH bracket is well posed;
  the single-component jump), **§4.4** (the kernel, and "What `ok` guarantees, and the near-pure
  class" — measured grid: at impurity ε ∈ {1e-12, 2e-12, 1e-9} every φ ≠ 0.5 is
  `ph_ill_conditioned` with |f| 2.6e-2…1.2e2 W; φ = 0.5 `ok` by coincidence, β = 1/2 from the
  provider's Rachford–Rice returning its first bisection midpoint; ε = 1e-6 all `ok`), **§4.7 (a)**
  (dormant: one exactly-zero equilibrium row per component, rank 15 of 18 on W0.8's mini-flowsheets;
  `branch_found` reports `TWO_PHASE`; the deferred remedy is a `ZERO_FLOW` regime pinning lifted
  flows at zero, dropping the equilibrium rows and adding `T_out − T_label = 0`), **§4.7 (b)**
  (single flowing component: EO rows regular for V, L > 0 — `V L (1 − K_k(T))` fixes T_sat, absent
  components' pairs have determinant `L + K_i V > 0`; the region path cannot reach it because ADR
  0005's screen and closure conversions take the regime from the provider's TP flash, which never
  reports `TWO_PHASE` for one flowing component (its liquid test comes first at T_sat, SYN-001
  §5.1); K04's independent split has the same blind spot; measured: valve P3 `ACTIVE_SET_CYCLING`,
  PH flash P4 `BOUND_BLOCKED`, control with 1e-6 mol/s of A converges), §15 A28–A30, §19 Q4, Q11, Q12.
- Rulings `docs/briefs/T05-rulings.md` §4 Q-R1, Q-R4, Q-R8 (the reasoning behind R-049/R-050).
- Register R-049, R-050 (`docs/decision-register.md`), R-007/R-008 (lifted split), R-029 (branch
  provenance / fingerprint), R-016 (verifier independence).
- ADR 0005 (`docs/adr/0005-*.md`; decision function D3–D4, lattice D2), ADR 0011 D1/D3.
- Code where the regime is taken from the provider's TP flash: `orchestrator/region.py` (`:279`,
  `_admissible` `:296`, `:642–651`), `orchestrator/phase_contract.py` (`decide` `:362`,
  `check_opening` `:230`), K04 `verify/checks.py:299, :654` and `verify/table.py:1002` (fresh flashes;
  independent split), the kernel `models/syn001/ph_kernel.py`.
- Schema fact: `schemas/solve-event.schema.json` already enumerates `ZERO_FLOW` in the
  `(unit_id, regime)` phase pairs; check `attempt-context`, `checkpoint`, `solution-certificate`
  before concluding a frozen schema must change.

## 4. Constraints and invariants

- `src/process_runtime/thermo/syn001.py` stays byte-identical (ADR 0011 D3 (i): its source hash is in
  every SYN-001 `model_version`, R-009). The provider's TP flash, including its Rachford–Rice, cannot
  be changed; a better-conditioned split, classification or near-pure flash must live in the unit
  layer / orchestrator / verifier, built on the provider's `lnK` and `h` and their derivatives.
- **Every existing registered result stays as registered**: SYN-001 bit-identical (identity document
  minus `t05` `b364bb3d…`, structural `4ce030ca…`, policy `21c44e10…`), T02–T04 fixtures, and
  T05's registered unit cases and C1–C3/C3X (their `t05` identity may change only where the design
  says why). A change meant to be inert must be proved bit-identical.
- K04's verifier shares nothing with the solver (R-016); its tolerances by kind and
  `check_policy_sha256` do not move unless the ADR says why (a new policy hash re-certifies nothing
  silently — say what it does to existing certificates).
- Residual and Jacobian paths describe the same function at the same state.
- Frozen interfaces (`docs/interfaces-frozen.md`): prefer none changed; if one must, the ADR states it,
  with migration — **flag it prominently in your reply**; the build lane reports it to Frank before
  implementing it.

## 5. Already decided, not open

Frank's directive (§1). Everything else in T05 (ADR 0011, the case family, the verifier table
design, R-045…R-048, R-051) stands.

## 6. Genuinely open (decide these)

1. **Near-pure PH (Q11).** A kernel route (and its EO face, if affected) that resolves a near-pure
   feed in the latent jump for every target — e.g. parametrizing the two-phase band by vapour
   fraction instead of T, with the split computed from the provider's K-values in the unit layer —
   with an acceptance criterion that is a real accuracy statement; what replaces A29; how K04's
   fresh-flash energy and independent-split checks judge such a state without the provider's
   ill-conditioned flash (R-016 still holds).
2. **Single flowing component on EO (Q12).** A regime classification that reports `TWO_PHASE` for
   one flowing component at `ln K_k = 0` inside the jump, for ADR 0005's screen/conversions and for
   K04's independent split; how the start (`initial_state`) and the attempt signature see it;
   what replaces A30.
3. **Dormant PH-type outlet (§4.7 (a)).** The `ZERO_FLOW` regime (pinned zero lifted flows, dropped
   equilibrium rows, label row), its place in the lattice and the decision function, the branch
   record/fingerprint (R-029), what the certificate reports (target: `VERIFIED` at a regular
   dormant root); what replaces A28.
4. Whether 1–3 share one mechanism, and the order of the build-lane chunks, each with its inertness
   proof for SYN-001/T02–T05.

## 7. How it will be verified

The gate (`PATH=.venv/bin:$PATH ./scripts/check.sh`, 2548 green on `main`), your new assertions
against the twin's 40-digit references, the inertness items above, CI on x86-64 and aarch64 (K05
identity job), a design-lane `reviewer` pass, and an evidence manifest `evidence/T05b/<commit>/`.

## 8. Out of scope

Q2 (exchanger phase change), Q3 (general two-phase mixer), Q7 (several reactions), Q8 (synthetic
formation data), Q9 (UA spec) — still at their defaults pending Frank's word; T04 F9; T06.
