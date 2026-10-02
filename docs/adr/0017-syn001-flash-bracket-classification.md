# ADR 0017 — SYN-001's TP flash classifies by its own Rachford–Rice bracket when the two binary64 tests disagree (F6), and SYN-001's identity is re-registered

> **FOR FRANK — this ADR moves SYN-001's identity.** It changes `src/process_runtime/thermo/syn001.py`, whose SHA-256 is in every SYN-001 `model_version` (R-009). Every SYN-001 flowsheet label, `model_version`, `plan_id`, K05's structural hash `4ce030ca…` and the `t02`…`t05b` identity keys move — **by the hash substitution only**: every number, outcome, event sequence, verdict and certificate check value of every registered result is unchanged (measured, D3). No frozen interface, schema, `Protocol` or ADR 0001 rule changes. It needs Frank's yes before it lands; until then everything else proceeds (D6).

**Status:** Accepted 2026-09-27 — T06's manifest `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` is `tested` (100 checks: 96 pass, 4 not_applicable with reasons; A29/A30 judged on scoring run 2, run 1's FAIL carried), after the design-lane review `docs/reviews/T06-review.md` and verdicts `docs/reviews/T06-verdicts.md`. Frank approved the SYN-001 identity move (2026-09-26); applied in W13 with A78's two-step proof. Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-26
**Author:** design lane (`specifier`); brief `docs/briefs/T06-amendment-2.md` §2 item 1 (F6).
**Directive:** Frank: fewest limitations; robustness.
**Normative text:** this ADR; `docs/derivations/T06-corpus-spec.md` §0 F6 and §13 A75–A79 (Amendment 2); registered states `ref.closed_form.f6_states`.
**Amends:** R-009's consequence for this one change (the label moves because the equations' implementation moved, which is R-009 working as designed); ADR 0011 D3 item (i) and ADR 0014 D8's "`4ce030ca…` must not move" are re-baselined to the post-ADR values from this ADR's commit on. **Supersedes:** T06 spec Q12's default ("no change to `thermo/syn001.py`").
**Affected requirements:** D08 (a provider answers every state in its declared domain), D20 (identity), V20 (robustness).
**Affected packages:** K02 (`thermo/syn001.py`), every package whose identity key or fixture carries a SYN-001 label (K03 fixtures, K04 fixtures, K05's structural hash and run-manifest fixture, T02–T05b identity keys), T06 (F4's C3 restart registration, the ensemble).

## Context

`Syn001Provider.flash` classifies a flowing feed as `LIQUID` if `Σ zᵢKᵢ ≤ 1`, as `VAPOR` if `Σ zᵢ/Kᵢ ≤ 1`, and otherwise solves Rachford–Rice on `[0, 1]`, whose bracket test is `f(0)·f(1) > 0 → not_converged` with `f(β) = Σ zᵢ(Kᵢ−1)/(1+β(Kᵢ−1))`. At a stream at its bubble point the exact `Σ zK − 1` is zero, and the two binary64 evaluations `Σ zK` and `f(0) = Σ z(K−1)` round on opposite sides of it: *measured* (build lane, C3's traversal pass 4 and NET-02's pass 29) `Σ zK = 1.0000000000000002` (two-phase) while `f(0) = −6.9e-17` (C3) / `−8.7e-18` (NET-02), so `f(0)·f(1) > 0` and the flash returns `not_converged`, "Rachford-Rice did not reach 1e-14 in 200 iterations" — at iteration 0, with a message that describes a different failure. The mirror case happens at a dew point.

*Measured for this ADR* (this host, `wp/T06` at `a01a9d4`, scratch probes, not committed): of 200 000 seeded feeds (`random.Random(20260926)`, `T ∈ [280, 440]` K, `P ∈ [5e4, 2e5]` Pa, `nᵢ ∈ [0, 1)`), 28 727 flash two-phase; re-flashing their products at the same `(T, P)` returns `not_converged` for **133 liquid** and **391 vapour** products (the build lane's 760-feed probe: 6 and 15). **Every one** has both bracket values of one sign (liquid products: both negative, `|Σ zK − 1| = 1 ulp`, `|f(0)| ≤ 8.5e-17`; vapour: both positive, `|Σ z/K − 1| = 1 ulp`, `|f(1)| ≤ 2.3e-16`). No flash fails by exhausting its 200 iterations: none among the 57 454 re-flashes, 8 624 two-phase feeds with trace compositions down to 1e-16, or 2 715 at the domain's corners (at most 13 iterations); exhaustion occurs only with K-values outside SYN-001's domain (`K ∈ [1e-8, 1e8]`, 16 %), which the provider never produces. The failure reaches the unit layer (the TP-state kernel's admissibility test and enthalpy, so a mixer, heater or flash on a saturated inlet), the revision region's kernel checks and the verifier's fresh flash; F4's restart initializer absorbed it only by truncating C3's sequence at pass 3.

## Decision

### D1. The fix (in `thermo/syn001.py`, nowhere else)

When `_rachford_rice`'s bracket test fails — `f_low·f_high > 0` with `f_low = residual(0.0)`, `f_high = residual(1.0)`, the values it computes today, not a recomputation — the flash **returns the single phase those signs name** instead of `not_converged`: both negative (`f_low < 0`) → `_single_phase(state, "LIQUID", k_values, 0.0)`; both positive → `_single_phase(state, "VAPOR", k_values, 1.0)`. The result is the ordinary single-phase result (same fields, no message). Nothing else changes: the two classification tests keep their arithmetic and order; a bracketed feed (`f_low·f_high ≤ 0`) runs today's iteration bit for bit; the exhaustion failure and its message stay (after the fix they are the only `not_converged` and the message is then true).

**Why this is correct.** The branch fires only where the first test put the feed two-phase (`fl(Σ zK) > 1`) and the bracket says it is not (`fl(f(0)) < 0`) — two binary64 roundings of one exact quantity that straddle zero, so the exact state is within roundoff of saturation and the exact vapour fraction is within roundoff of 0 (or 1). At the two registered states (`ref.closed_form.f6_states`, twin at 40 digits) the liquid product is 1.09e-14 K above its bubble point with exact `β = 1.16e-15`, and the vapour product 2.6e-14 K below its dew point with exact `1 − β = 5.6e-16`; the fixed answers `β = 0` and `β = 1` are within 1e-14 of exact (claim `F6.fixed_answer_within_1e-14_of_exact_beta`) — a flow error below 1e-15 mol/s against the 3.1e-7 mol/s allowance. ADR 0001 D3.4 already names this result: a flowing feed whose split has `V = 0` is `LIQUID` with a dormant vapour outlet.

### D2. What moves, and what does not

| Moves (by the hash substitution) | Does not move |
| --- | --- |
| `PropertyCapabilities.implementation_sha256` (full); the exact property-cache keys; certificates' `independence_qualifications[*].implementation_sha256` | `data_sha256`, `constants_sha256`, `configuration_sha256`, `variable_ids`, `state_sha256`, `revision_sha256`, `policy_sha256`, `check_policy_sha256` |
| the 12-hex segment of every SYN-001 label (`SYN001-fs1-…` and `FSR1-…`), hence every `model_version`, `plan_id`, K05's `structural_sha256` `4ce030ca…` and `artifact_r0_sha256`, and every identity key carrying them (`t02`…`t05b`, and `t06` when emitted) | every float, outcome, event kind and sequence, verdict, check id and result, regularity status, root fingerprint of every registered result; every `ok` flash result anywhere |
| every committed round-trip fixture carrying a label or the hash (11 files at `a01a9d4`), regenerated by its R-015 generator | — |
| C3's restart start (F4): 3 passes with F6's rejection → **8 passes, no rejection** (measured; it converges to C3's root, worst 3.5e-4 of an allowance, `S3.T`, under `T05b-v2` and `T05-W13`) | every other G6 case (8 passes, unchanged) |

*Measured for this ADR*: the whole suite with D1 applied by monkeypatch and the label left unchanged: **3 375 of 3 378 pass**; the three failures are exactly F6's own registrations (`test_wo3_c3_is_truncated_at_pass_4_by_u_mix` and G6's two C3 cases, which assert the truncation). The re-flash probe: 0 `not_converged` of 57 454 (524 before), each of the 524 through D1's branch, and every other result count-identical.

### D3. The inertness proof the change must carry (one isolated commit)

1. With `_implementation_sha256` monkeypatched to return the **old** hash, every identity document (`scripts/k05_structural_identity.py`, the `t02`…`t05b` keys), every committed fixture regenerated by its R-015 generator, and every registered trace and certificate are **byte-identical** to their values before the commit; the full suite passes except F6's three registrations, which are re-registered (D4).
2. With the real hash, each moved value differs from its pre-commit value exactly as D2 says: label-bearing strings by the substitution old 12-hex → new 12-hex (and the full hash where the full hash appears), derived digests recomputed. The new structural hash and each new key digest are recorded in the T06 manifest and in `docs/T06_DECISIONS.md`, and from this commit on every "must not move" clause (ADR 0011 D3, ADR 0012, ADR 0013, ADR 0014 D8, T06 spec §10) refers to them.
3. The CI identity job passes on the registered pair (x86-64 and aarch64 compute the same new keys).

### D4. Registrations that change

- F4's WO3 test and G6's C3 expectation: `passes_used == 8`, `rejected == ()` for C3 (every G6 case now keeps all eight passes).
- T06 spec §0 F6 and Q12: closed by this ADR.
- New regression assertions A75–A79 (spec §13): the two registered states return `LIQUID`/`VAPOR` with the flowing outlet equal to the feed bit for bit; a seeded re-flash probe returns no `not_converged`; the proof of D3.

### D5. If Frank declines

F6 stays, as a registered limitation: C3's restart keeps its three-pass truncation; an ensemble start that meets F6 is `F-TYPED(<its outcome>)` under its own word; §15 records that SYN-001's TP flash reports `not_converged` for a stream within one rounding of saturation. No wrapper is written (see *Alternatives*).

### D6. Ordering while Frank's answer is pending

Everything independent proceeds (ADR 0016, the generator, W3/W4/W5/W8 items). The ensemble's starts file may be generated before the answer: D1 changes only results that are `not_converged` today, so a start whose assembly recorded no rejection with a `not_converged` status cannot change; if any recorded rejection names `not_converged`, the starts are regenerated after the fix lands. The starts file records no provider identity (spec §6.5's list), so the identity move does not touch it. **The scoring run (W6/WO9) runs on the provider as it will be scored** — after the fix lands, or after Frank declines.

## Alternatives considered

- **(b) A unit-layer and verifier-layer wrapper** that re-classifies a `not_converged` flash by the bracket signs. Rejected: the failed `FlashResult` carries neither K-values nor an iteration count, and its message is the same for both failure modes, so a wrapper must recompute `z`, `K` and `f(0), f(1)` outside the provider — a second implementation of the provider's classification in at least five call sites (the TP-state kernel, the region's two kernel checks, the verifier's two fresh flashes; R-016 forbids the verifier sharing the unit layer's copy) whose rounding need not match the provider's, so it can re-create the disagreement it exists to remove. Every other consumer (T07, K05 replay, any new unit) would still see the defect. It keeps the identity by leaving a known defect in the component that owns it.
- **Classify by the bracket signs everywhere** (replace `Σ zK ≤ 1` by `f(0) ≤ 0`). Rejected: it changes `ok` results at states where the two tests disagree the other way (today `LIQUID`, then two-phase with `β ≈ 1e-16`), so registered traces and certificates could move in their floats. D1 changes only what fails today.
- **A bracket-collapse termination** (accept when `low` and `high` are adjacent doubles). Not needed: no exhaustion was found in SYN-001's domain; it would add an untested branch. Revisit if a probe ever finds one.
- **Loosening `_TOLERANCE`**. Rejected: the failure is at iteration 0; the tolerance is not involved.
- **A second provider (`syn001-v2`) beside the first.** Rejected: it forks the fixture and its identity for a one-branch fix, and every case would have to choose.
- **Leaving it (Q12's default).** Rejected on Frank's steer: a typed failure on a state with a well-defined answer is a limitation the provider can remove, and it costs the robustness evidence (F4's C3 restart, ensemble starts through saturated recycles).

## Consequences

- C1. No frozen interface, schema, `Protocol`, ADR 0001 rule, tolerance or check-policy byte changes. The identity move is ADR 0002 D2.7 / R-009 working as designed: the label changes because the equations' implementation changed.
- C2. Replay bundles and caches made before the commit are refused for identity (the correct behaviour); no committed bundle is replayed across it except through regenerated fixtures.
- C3. Closed packages' evidence manifests keep their recorded values (they are records of their commits); the re-baseline is recorded in T06's manifest.

## Acceptance evidence

A75–A79 in `evidence/T06/<commit>/manifest.json`; D3's two-step proof; the twin's claims `F6.*` pass; the CI identity job green on both architectures with the new keys.

## What this ADR does not establish

That the provider has no other defect; that a bracketed Rachford–Rice iteration never exhausts (only that no probe found one in the domain); anything about PH flashes (none in the provider) or other providers.
