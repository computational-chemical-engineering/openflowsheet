# ADR 0011 — The T05 unit models: the PH closure lives in the unit layer, `SYN-001-ref-v1` is a formation datum, and SYN-001 stays bit-identical

**Status:** Accepted 2026-09-25 — T05's manifest `evidence/T05/91ac0103c1040175560d74d9afa2a091a8d25b2d/manifest.json` is `tested` (31 of 31 checks, A00–A30; A23's structural hash and A24's `t05` identity measured on the CI pair, run 36085409305), after the design-lane review `docs/reviews/T05-review.md` (no must-fix), the ruling round `docs/briefs/T05-rulings.md` and their fixes. D3's six bit-identity items hold; ADR 0004 D3.3 was amended on the way (one guarded factorization). Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-25  
**Author:** design lane (`specifier`); plan §1.3 assigns every ADR, the reference states and the sign conventions to the design lane  
**Normative text:** `docs/derivations/T05-unit-models-spec.md` §4 (D1), §6.1 (D2), §17 and §15 A23 (D3); machine-readable expectations `benchmarks/t05/reference_values.yaml` from `docs/derivations/scripts/t05_reference.py`  
**Affected requirements:** D08 (a unit requires the capabilities it uses, not a tier), V12 (the unit library), D14 and A09 (energy checks for reacting units, and what they may claim), D20 (no existing identity moves)  
**Affected packages:** T05 (implements everything below); K02 (its provider and its six models are not edited; its mixer keeps its registered restriction); K04 (its check policy hash must not change; T05 §12 adds per-model checks); K05 (its structural hash must not change); T06, T08 (read D2 when comparing or replacing a reactor)  
**Blueprint authority:** §5.1 (native equation models and causal evaluators), §5.3 (a replacement checks reference states and conserved quantities — "matching the label 'reactor' is insufficient"), §6.1 (capabilities are queried, not graded), §6.2 (PH flash: bracketed, explicit single-phase endpoints, zero components)  
**Companions:** ADR 0001 D5 (reference conventions; extended, not changed, by D2), ADR 0005 D2 (one regime per phase-selecting unit; kept by T05 §3.4's invariant), ADR 0008 D3 (accumulation declarations; T05 §13.2 extends the registered table to the new manifests), R-009 (the provider's source hash is in every SYN-001 `model_version`), `docs/interfaces-frozen.md` §1–§3

## Context

T05 must deliver a general PH flash, a conversion reactor, a component separator, a valve, a liquid pump and one two-stream exchanger. Three of them fix an outlet temperature by an energy balance rather than a specification, which K02's units never did, and SYN-001's provider offers only a TP flash (`flashes = ("TP",)`, "no PH flash in v0.0"). The reactor needs an enthalpy of reaction, and ADR 0001 D5.1 fixed SYN-001's reference state for a system that had no reaction: `h_i^L(T_r, P_r) = 0` for each component, with nothing said about whether those zeros share a datum. Two frozen facts bound every choice: `FlashRequest` carries a `StreamState` and nothing else, and `thermo/syn001.py`'s source hash reaches every SYN-001 `model_version` through the flowsheet label (R-009), so any edit to that file moves every registered SYN-001 identity.

## Decision

### D1. The PH closure is a unit-layer formulation; the provider gains no capability

A PH-type outlet is K02's lifted TP-state outlet (R-008) with its temperature a free column and an energy row fixing it; its causal evaluator solves `Ḣ_TP(n, T, P) = H*` by a bracketed kernel on the provider's existing TP flash, with a saturation route for a single flowing component (T05 §4). No field of `FlashRequest`, `FlashResult` or `PropertyCapabilities` changes; `PropertyCapabilities.flashes` stays `("TP",)` for SYN-001 and its limitation text stays true; `src/process_runtime/thermo/syn001.py` is not edited. A T05 unit requires `flashes ∋ "TP"`, `properties ⊇ {h, lnK}` (or `{h}`) and first derivatives in `T` and `P`; the monotonicity of `Ḣ_TP` in `T` that the kernel's bracket relies on is a property of the provider class, derived for SYN-001 in T05 §4.2 and stated in each manifest's limitations, because no capability field can carry it without changing a frozen field set. The K02 mixer is not generalized.

### D2. `SYN-001-ref-v1` is a formation datum; reactors balance total enthalpy

The pure liquids A, B and C have **equal (zero) formation enthalpy and formation Gibbs energy at `(T_r, P_r)`**. With it, `Σ ν_i h_i` is an enthalpy of reaction. This is a declaration — the pseudo-components have no elemental composition — and it changes no number anywhere. Consequences (T05 §6.1, generator-checked): equal molar masses force `Σ ν_i = 0` for every mass-conserving reaction; every liquid reaction on SYN-001 is exactly thermoneutral at every `(T, P)`; a vapour reaction has `Δh_r = Σ ν_i L_i`; `Δg_r^L = 0` (recorded for a future equilibrium reactor). Every reacting unit writes its energy balance in total-enthalpy form, `Q + Ḣ_in − Ḣ_out = 0`, and never adds a separate `ξ Δh_r` term. A reacting unit is constructed only over a provider whose `reference_convention` is in the **registered reaction-consistent set**, today `{"SYN-001-ref-v1"}`; otherwise construction raises `SpecificationError` with the code `reference_convention_not_reaction_consistent(<convention>)`. Extending the set takes a new decision recorded the same way, naming the convention's datum.

### D3. SYN-001 stays bit-identical, and the generalizations T05 needs are proved inert

T05 adds files and generalizes three SYN-001-specific mechanisms — the flowsheet assembly and traversal, the orchestrator's lifted-split registry (`syn001_lifted_splits`), and K04's check set — so that new units plug in by declaration. The binding rule: **every existing SYN-001 result is bit-identical after T05**, shown, not assumed, by (i) `thermo/syn001.py` byte-identical to `main` at `279b2eb`; (ii) every K02–T04 test passing unchanged; (iii) K05's structural hash unchanged on the CI pair; (iv) K04's registered `check_policy_sha256` unchanged — T05 adds no quantity kind and no tolerance, so shaft work uses the `heat_rate` scaling class while its manifest `Quantity` kind is `power`; (v) the two SYN-001 lifted-split descriptors unchanged; (vi) every committed fixture regenerated identically by its R-015 generator. Any one failing is a defect in the generalization, never a re-registration. No schema changes; no new check category; no new `SolveEvent` outcome.

## Alternatives considered

- **A provider PH flash (`flashes` gains `"PH"`).** Rejected: the target enthalpy has no field in `FlashRequest` (a frozen field set would change), the provider's source edit would move every SYN-001 `model_version` (R-009), and an opaque inner solve returning implicit derivatives is exactly what R-008 rejected for the lifted split.
- **Both a provider PH and a unit formulation.** Rejected: two descriptions of one function, which the residual/Jacobian identity rule exists to prevent, and all of the first alternative's costs.
- **Generalizing the K02 mixer onto the PH closure in place.** Rejected: a lifted outlet adds variables and rows, which changes `model_version` of every SYN-001 result; a general mixer can be a new model on the same kernel when a registered case needs it (T05 §19 Q3).
- **Synthetic formation data** (a new convention `SYN-001-ref-v2`, or a second provider with nonzero formation enthalpies), so that a liquid reaction is not thermoneutral. Rejected for v0.1: an edit to SYN-001's data moves every identity; a second provider forks the fixture and its oracle for a test the vapour and two-phase cases already give (a reactor that drops the reaction from its balance fails RX-2 by 7 500 W). Reconsidered if Frank wants a non-thermoneutral liquid reaction before T08 (T05 §19 Q8).
- **A registered thermoneutral reactor without declaring the datum.** Rejected: `Σ ν_i h_i` would be a number with no meaning, and a replacement reactor (blueprint §5.3) would have nothing to check its reference state against.
- **A heat-of-reaction term beside sensible enthalpies.** Rejected: on a formation datum it double-counts; without one it needs data SYN-001 does not have.
- **A reaction-consistency capability field on `PropertyCapabilities`.** Rejected: a frozen field-set change for a fact the reference-convention identifier already carries once the set is registered.
- **A new scaling kind `power` for shaft work.** Rejected: K04's `check_policy_sha256` hashes the tolerance table by kind, so a new kind changes it for every existing certificate, for identical numbers.

## Consequences

- C1. No frozen interface, schema, check category or tolerance changes. `docs/interfaces-frozen.md` needs no entry beyond a one-line note under §3 that ADR 0001 D5's convention `SYN-001-ref-v1` now also carries D2's declaration, when this ADR is accepted.
- C2. `PropertyCapabilities.flashes` of SYN-001 remains `("TP",)`. A future provider that offers `"PH"` is not consumed by T05's units; if one is ever used, it is a replacement under blueprint §5.3 with its own manifests.
- C3. T05's six manifests name `reference_convention: SYN-001-ref-v1`; the reactor's energy checks carry D2 beside [A09] in their `independence_qualification`.
- C4. Register entries R-036 to R-043 (`docs/decision-register.md`); R-044 records T05's case family, which is not an ADR matter.
- C5. Handed on: a general two-phase mixer (T05 §19 Q3); several reactions per reactor (Q7); synthetic formation data (Q8); the dormant-flow singularity of energy-determined temperatures (T05 §4.7, Q4), whose remedy — a regime-conditional label row — would amend ADR 0005's regime lattice.

## Migration and bit-identity evidence

There is nothing to migrate: no stored document changes meaning. The evidence that no existing result moved is T05 assertion A23, measured in `evidence/T05/<commit>/manifest.json` and on the CI pair (K05's identity job): the six items of D3, each compared with its value recorded before any T05 edit (T05 W0.1).

## Acceptance evidence

- T05 assertions A00–A27 in `evidence/T05/<commit>/manifest.json` with `status: tested`; in particular A07–A12 (the PH kernel and the six models), A10 (the convention refusal, RX-S4, with a provider test double), A13 (PH ∘ TP = identity), A21–A22 (the checks and injections of T05 §12), and A23 (bit identity).
- `t05_reference.py --check` passes and the committed reference file's SHA-256 matches the specification's header.
- The gate is green on x86-64 and aarch64 with K05's structural hash unchanged.
