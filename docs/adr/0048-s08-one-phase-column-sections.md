# ADR 0048 — One-phase column sections: block openings in the column's initializer; ADR 0005 D4 unchanged

**Status:** Proposed 2026-10-25.
It becomes Accepted when:
1. S08's evidence manifest is `tested`;
2. gates G1 and G2 of `docs/derivations/S08-design.md` §9 have passed on the merge candidate;
3. `scripts/gate.sh` has passed, and CI is green on x86-64 and aarch64;
4. the `reviewer` has read this ADR.

**Date:** 2026-10-25
**Author:** design lane (`architect`). Brief: `docs/briefs/S08-one-phase-sections.md`.
**Normative text:** `docs/derivations/S08-design.md` §5–§9.
**Evidence:** `docs/derivations/scripts/s08_design/measured.txt`.
**Decides against:** ADR 0005 D4, which is **not** amended. This ADR records why.
**Amends:**
- S02 §7: adds step 7, the block re-entry.
- S02 §8: adds item 6, two-phase saturation consistency.
- S02 A12: narrowed to its `CONVERGED` branch for P1.
- R-632's limitation: narrowed (R-639's queued package).
- R-632's two rejections stand. Neither is reversed.

**Affected packages:** S08, which implements this ADR; S02 (P1's record, A12, §7, §8); S03 (the limitation sentence only).
**Unaffected:** T03, T05b and every other user of `orchestrator/phase_contract.py` and `orchestrator/region.py`. No code there
changes.

## Context

A SYN-001 column whose regular root has a `VAPOR` or `LIQUID` section ends in a typed failure. S02's P1 is a liquid heater
dressed as a stripper; its root is L×5. P1 ends `HOMOTOPY_STALLED`.

S02 §4.3 proves the block rule: a regular signature reads `V^a 2P^b L^c`. R-533, R-554 and R-632 twice declined to teach the
rule to ADR 0005 D4's single decision function, and declined a screen around `solve_region`. R-639 queued this package, with an
ADR against D4 as an entry condition.

## Decision

**D1. Route.** The column does not learn the block rule inside the contract. It learns it in its initializer.
- When today's path ends typed (S08-design §5.1, set `T_B`), or converges onto a near-trivial split (D3), the column builds
  block-conforming openings `V^a 2P^b L^c` from its sources.
- Sources are liquid or vapour inlets, condenser and reboiler, and intermediate duties (§5.2).
- It solves from each opening in a fixed order, under the unchanged contract, policy and edge 3, and returns the first accepted
  root.
- The opening of attempt 0 is the initializer's under ADR 0005 D2–D3: it is not screened, and its source is `initializer`.
  Choosing a block opening therefore adds no decision inside the attempt loop.
- D4's "one function, called by both controllers" still decides every restart of every attempt.

**D2. The block endpoint `s08-block-endpoint-v1`** (§5.3).
- The core: S02 §18.2's bubble-point sweeps, restricted to the core.
- Single-phase stages: explicit passes at the specified duties, liquid top-down and vapour bottom-up.
- Exact `+0.0` pins, so the region opens each stage in the candidate's regime.
- An admissibility check of every block stage.
- A refusal skips the candidate and never ends the solve.

**D3. S02 §8 item 6.**
- Every `TWO_PHASE` stage of an accepted state lies within `τ₆ = 1e-4 K` of both the bubble temperature of its liquid and the
  dew temperature of its vapour.
- A `CONVERGED` answer that fails only item 6 triggers D1. Otherwise it is a §8 defect, as today.

**D4. Records.**
- `ColumnSolution.reentry` holds Stage A's record and every candidate's record. It is `None` when D1 does not run.
- The top-level fields describe the returned solve.
- The certificate's `initializer_source` names `s08-block-endpoint-v1`. That field is a free string, so this is no schema change.
- There is no new `SolveOutcome`, cause grammar, `SolvePolicy` field or schema field.

**D5. Bit-identity.**
- Stage A is today's code path. D1 runs only after Stage A fails.
- The registered Stage-A failures are P1, U1 and U2. U1 and U2 generate no candidate.
- Only P1's record moves, and its Stage-A part equals today's record exactly (G1).
- No file under `orchestrator/`, `numerics/`, `thermo/`, `compile/` or `schemas/` changes (G2).

## What changed since R-632

1. **A registered use case exists**: P1, now joined by P2, P3, F1 and D1 (§6).
2. **Measured: the binding constraint is the restart opening, not the block rule.** *Amended 2026-10-26 (S08-design §13.1,
   R-733): every measured failing restart has a signature with no regular root, because it fails §5.2 (V2). The evidence
   does not separate the opening from the signature. The route stands, because it solves only (V2)-valid signatures.*
   - A block closure inserted into the contract does not rescue P1. Attempt `(2P, L, L, L, L)` ends `LINE_SEARCH_FAILED` after 0
     iterations, both with and without an energy-consistent rebuild of the closed units.
   - P3's contract restart `(2P, 2P, 2P, 2P, L)` already conforms, and it fails the same way.
   - Block openings converge P1, P2, P3, F1 and D1 in 0, 0, 4, 4 and 5 Newton iterations.
3. **The route lies outside the contract.** R-632's objections, "model structure inside the single decision function" and "a
   second decision function", do not apply. The contract's code does not change.

## Alternatives considered

- **A block rule in D4** (closure of each proposal, with model-declared stage chains). Rejected:
  - measured insufficient (P1, P3), because its openings inherit the failed attempt's state;
  - it changes the shared function;
  - it moves records wherever a column's walk passes a non-conforming proposal that has a regular closure.
- **A model-side screen around `solve_region`.** Rejected: it has the same opening problem, and it is a second decision function
  (R-632).
- **A homotopy that switches signature.** Rejected:
  - edge 3 is frozen-signature, and stalls on P1, P2 and P3;
  - for P1's topology no regular signature lies between 2P×5 and L×5;
  - it would be a T04-scale design.
- **Topology first** (opening dead sections single-phase before trying all-2P). Rejected: it would move every unregistered
  case that converges today onto a new path. It remains a possible later performance step.
- **A thermal predictor in Stage A.** Rejected: a misprediction on a near-boundary case breaks bit-identity.
- **A new ADR 0010 recovery edge.** Rejected: it moves column structure into the generic recovery ladder.
- **Enumerating every `V^a 2P^b L^c`.** Rejected: O(N²) solves, and root selection by search.

## Consequences

- C1. P1 returns `CONVERGED` at its closed form. S02 A12 asserts that branch for P1. The held typed branch becomes
  `reentry.stage_a`.
- C2. F1-like columns, whose all-2P path converged to a near-trivial split, now reach their block root. A near-trivial split is
  never returned as a success.
- C3. S03's limitation is narrowed to block roots that S08's §5.2 does not generate.
- C4. Findings handed on as follow-ups, not acted on here (S08-design §3, §10 Q3 and Q4):
  - F5: dotted column unit ids are read as dormancy items in `adjacent` and `_changes`.
  - F4 at contract level: `_admissible` accepts any `TWO_PHASE` branch.
- C5. S01's `solve_cascade` and its `not_two_phase` gate are unchanged. P1 never meets that gate.
- C6. Register entries R-728 to R-731.

## Acceptance evidence

- S08.A01–A16 in `evidence/S08/<commit>/manifest.json`, with `status: tested`.
- G1: `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`.
- G2: empty.
- `s08_reference.py --check` passes.
- The full gate passes, and CI is green on both architectures.
