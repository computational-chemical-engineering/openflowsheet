# ADR 0015 — Recovery edge 3, second action: sequential re-initialization of a revision-built region

**Status:** Accepted 2026-09-27 — T06's manifest `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` is `tested` (100 checks: 96 pass, 4 not_applicable with reasons; A29/A30 judged on scoring run 2, run 1's FAIL carried), after the design-lane review `docs/reviews/T06-review.md` and verdicts `docs/reviews/T06-verdicts.md`. Frank approved its two additive enum widenings (2026-09-26). Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-26
**Author:** design lane (`architect`), T06 F4; committed by the build lane as the design lane's text (design note `docs/design/T06-F4-recovery.md`, Appendix A).
**Normative text:** `docs/design/T06-F4-recovery.md` §5 (the trigger and preconditions P0–P5, the restart initializer, the action, the records, the seams).
**Amends (additively):** ADR 0010 D1 (a new value of `globalization.eo_recovery`), D3 (edge 3's action set) and D7 (the `eo_recovery_unsupported` reasons). **Reverses:** nothing registered.
**Affected requirements:** D01 (recovery edges named by the policy), V20 (robustness), D20 and blueprint §8.3 R0 (new values classified).
**Affected packages:** T06 (the ensemble's revision policy, NET-02's registration), T02 (executor), T04 (edge 3's action set, which ADR 0010 D1, D3 and D7 extend additively), T05 (`revision.py`'s initializer), T07 (the application default, design note §9 Q2).
**Blueprint authority:** §7.4 (initializer order, checking every candidate), §7.7 (EO globalization failure: another globalization; invalid trial: reinitialize; every fallback edge states a trigger, preconditions, a count, a cost, a checkpoint policy and an outcome).

## Context

NET-02 ends `BOUND_BLOCKED` at iteration 1 from `traversal-G0-v1`, and edge 3 has no continuation parameter on a revision region. The measured cause is a wrong-signed Newton step in the recycle's inventory mode at the two-pass start (`cond Ĵ = 2.4e4`; `ΔS3.L = −568` mol/s, while the root's recycle `ΣS6` is 33 mol/s above the start's). One more sequential pass fixes the sign, and every start from 3 to 28 passes converges (design note §2).

## Decision

- **D1.** `globalization.eo_recovery` gains the value `homotopy_or_sequential_restart`, and the default stays `homotopy`. Under the new value, edge 3's action is the specification continuation if the region has a continuation parameter; else the sequential restart if the flowsheet is revision-built, its restart initializer builds, and the restart start is not the failed item 0's start by construction; else `unsupported(<reason>)`. The trigger set and `eo_recovery_max_count = 1` are unchanged.
- **D2.** The restart initializer `traversal-G0-pass8-v1` is the traversal from dormant tears continued to 8 passes. A failing pass `j ≥ 3` truncates the sequence to pass `j − 1` and is recorded. Passes 1–2 must succeed, as `traversal-G0-v1`'s do. Like every initializer, it is unmetered (T05 §2.2).
- **D3.** The action is one region solve from the restart start. It gets §6.2's projection, the policy's core and contract, and a fresh contract state. Its first item has `opening_source = eo_recovery_start` and `initializer_source = traversal-G0-pass8-v1`, and its items continue the failed solve's provenance densely. The outcome is the restart's, and the certificate judges the target declaration (R-035).
- **D4.** `solve-event`'s `eo_recovery_unsupported` gains `no_restart_initializer`, `restart_start_unchanged` and `restart_initializer_failed`. Each is R0.

## Alternatives considered

- Split-fraction or tear-connection continuation: its coverage is limited, or its level identity contradicts ADR 0010 D2 and ADR 0008 D1.
- PTC mappings for T05 units: experimental, with derivations not done (ADR 0010 D5 stands).
- A projected or bound-aware Newton step: measured to collapse the recycle, and it would move K03 trajectories.
- A longer registered initializer: it moves every registered trace.
- Seeding from the failed opening's torn values: measured to be refused by the mixer's pressure rule in 11 of 11 cases.
- An adaptive pass count: its decision is a float and it is unneeded.
- A restart ladder: more than one recovery per step.
- Folding the restart into `homotopy`: a silent change of a registered value's meaning.

## Consequences

- Two additive schema enum widenings, with fixtures regenerated identically. **Approved by Frank on 2026-09-26** (frozen interfaces; `docs/interfaces-frozen.md` §2).
- The T06 ensemble's revision path runs `T06-revision-v1` (`T05b-v2` with only `globalization.eo_recovery` changed).
- NET-02 is registered `VERIFIED` under it, with `BOUND_BLOCKED` as the edge-off control.
- Every existing policy, trace and identity key is unchanged.

## Acceptance evidence

The design note's G1–G7. T06's manifest lists them; G8 is T06's gate. Register entry R-075.
