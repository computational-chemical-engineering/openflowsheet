# ADR 0072 — RRC: recovery edge 3 for a revision-built region continues the revision's changed operating values from the nearest verified ancestor, before the sequential restart, under a new opt-in policy value

**Status:** **Proposed, 2026-11-08.**
- It takes effect on `main` when four things hold:
  - Frank has approved the three additive schema widenings (FQ1);
  - RRC's evidence manifest is `tested` (gates G1–G10, F1 and F2 of the design note);
  - the design-lane `reviewer` pass is done;
  - `scripts/gate.sh` and CI on both architectures have passed on the merge candidate.
- Until then RRC is built on `wp/RRC`.
- Register entries are added on acceptance (drafts below, unnumbered).

**Author:** design lane (`architect`). **Brief:** `docs/briefs/RRC-architect.md`.
**Design note:** `docs/design/RRC-revision-region-continuation.md` holds the normative detail; § numbers below refer to it.

**Amends (additively):**
- **ADR 0010 D1:** `globalization.eo_recovery` gains `homotopy_or_revision_continuation_or_sequential_restart`. It is
  never the default.
- **ADR 0010 D2:** a second applicability, *revision continuation*, with the same map, controller, identity rule and
  frozen signature. `p⁰` and the opening come from a verified ancestor (§5.1).
- **ADR 0010 D3:** the action set under the new value (§5.5). The trigger set, as amended by ADR 0044 D1, and the count
  of 1 are unchanged.
- **ADR 0010 D7.3 and D7.5:** `continuation.type` gains `revision_continuation`.
- **ADR 0015 D1:** under the new value, revision continuation precedes the sequential restart.
  `homotopy_or_sequential_restart` is unchanged.
- **ADR 0024:** a second consumer of the lineage store, with selection `store-nearest-verified-ancestor-v1` and a
  `solve-path.json` member `revision_continuation` following D4/D5's pattern. Warm starts are unchanged.

**Supersedes in part:** R-827's "no revision region has one", and only under the new value. S11.A24′ stays true under
every registered policy.
**Does not amend:** ADR 0044, ADR 0008, ADR 0019, the request schemas, the `ApiError` codes, `eo_recovery_unsupported`,
K03, K04 and `verify_revision`.
**Affected requirements:**
- D01 (recovery edges named by the policy) and V20 (robustness);
- D20 and blueprint §8.3 (new values classified);
- blueprint §7.4 (initializer order) and §7.7 (every edge states a trigger, preconditions, count, cost, checkpoint policy
  and outcome).

**Affected packages:**
- RRC builds it;
- T04 and T06 (edge 3), T08 (lineage store, replay) and S11 (L-COL-9) are touched by new branches only.

## Context

A revision plan is one EO region over every row-authoring unit, started from `traversal-G0-v1`. The traversal satisfies
every specification row and every unit row, so the residual at the start lies only on the torn closure (T06-F4 §2,
measured on NET-02). No re-binding of pinned inputs makes that start a root. ADR 0010 D2's construction `p⁰ = x⁰[v]`
therefore gives an empty path on a revision region. Edge 3 records `unsupported(no_continuation_parameter)`, or runs ADR
0015's restart (L21, L-COL-9, R-827). Frank's Q30 (2026-10-27): "Plan for it at the appropriate time."

A physical easy endpoint has to be a known root. For a revision one exists: a `VERIFIED` solve of an ancestor with the
same declaration structure. The ADR 0024 store already holds such solves, and records them so that they replay.

## Decision

- **D1. Policy.**
  - The new value runs edge 3's actions in this order: specification continuation (ADR 0010 D3); else revision
    continuation (D2–D4); else the sequential restart (ADR 0015 D1–D3); else `unsupported(<restart reason>)`.
  - There is still one recovery region solve per step. A revision-continuation refusal before any attempt opens is a
    precondition failure: it is recorded, and the restart follows.
  - It is offered as `RRC-revision-v1`, which is `T06-revision-v2` with only this value changed. The `revision_eo`
    default stays `T06-revision-v2`.
- **D2. The continuation.**
  - `H(x, λ) = F(x; p(λ))` with `p(λ) = p* + (1 − λ)(p_src − p*)` over `D`, the pinned-input ids whose canonical values
    differ between the source declaration and the target declaration.
  - Each λ < 1 level is a re-binding of the target declaration, formed exactly and rounded once. λ = 1 is the target
    instance.
  - The λ = 0 level's `(model_version, constants_sha256)` must equal the source certificate's.
  - The opening is the source's certified root, in that certificate's final signature, held to T03 §5.1's
    `check_opening`. The signature is frozen along the path.
  - The controller, the corrector and the budgets are ADR 0010 D2's, unchanged. A phase boundary or fold on the path ends
    `HOMOTOPY_STALLED`, bracketed. Nothing at λ < 1 is target-verified.
- **D3. Source.**
  - Selection is `store-nearest-verified-ancestor-v1`: ancestors in `parent_revision` order, the target excluded, each
    checked with ADR 0024's predicate. The first hit wins.
  - Assembly checks, in order:
    - integrity: the state digest equals the certificate's `full_state_sha256`;
    - source identity: binding the ancestor reproduces its certificate's identity;
    - continuable: every document difference is a value change of a registered operating specification (§5.4,
      default deny).
  - The application performs the lookup. The orchestrator never reads the store.
- **D4. Preconditions at the edge**, the first failure deciding (§5.5–§5.6):
  - the flowsheet is revision-built;
  - a source was supplied;
  - equal `model_version`;
  - `D` is non-empty;
  - the λ = 0 identity holds;
  - signature coverage;
  - the opening check.
- **D5. Records.**
  - **Trace:** existing kinds only. A refusal is one `initializer_rejected` event,
    `revision_continuation_<absent|rejected>: <reason>`.
  - **Certificate:** the recovery item has `initializer_source = "revision_continuation_source"` and an
    `opening_state_sha256` equal to the source root's.
  - **Attempt context and certificate `continuation`:** `{type: "revision_continuation", parameter_ids, …}`.
  - **`solve-path.json`:** gains `revision_continuation` (§5.8), written iff the policy names the value. It is R0 except
    the provenance ids, the document body and the state values.
  - **`run.identity.r0_projection`:** one branch.
- **D6. Replay.** The rerun rebuilds the source from the member. It does no lookup and no binding. It re-runs the
  integrity and continuable checks and the edge's checks. A bundle replays alone.
- **D7. Schemas (FQ1).** Three additive widenings:
  - `solve-policy` `globalization.eo_recovery`;
  - `attempt-context` `continuation.type`, from a `const` to an enum;
  - `solution-certificate` `branch_provenance[].continuation.type`, likewise.

## Alternatives considered

The design note §4 gives the full table. In brief:
- **Specification rows on revision regions:** the path is empty, because the traversal satisfies them, and every plan
  changes.
- **Tear-connection homotopy:** the levels are not re-bindings of the target, and a new identity ADR would be needed.
- **Split-fraction from `r = 0`:** it covers splitter loops only, and the λ = 0 root is in a `ZERO_FLOW` signature, so
  the active set would have to change.
- **Global Newton homotopy:** ADR 0010.
- **Heuristic easy values:** no known root, and the values would be tuned on the cases they rescue.
- **Partial continuation:** λ = 0 is then not the ancestor's problem.
- **Nearest by a parameter distance:** a float decision.
- **Arclength:** not the only sound form; deferred.
- **Restart first:** continuation would never be reached where it is needed.
- **A two-recovery ladder:** FQ3.
- **Re-solving the ancestor inside the edge:** no certified anchor.
- **A lazy store callback:** a second store seam.
- **Folding into an existing value:** a silent change of meaning.
- **Default on:** moves every revision identity (FQ2).

## Consequences

- **C1. Bytes that move:**
  - the three schema files;
  - measured by WO-1 (`docs/RRC_DECISIONS.md`): the three schema files' SHA-256 move and nothing else that is
    digested — `schemas/registry.json` (a file list), the served MCP tool-list digest (`455d01eb…`), every offered
    policy's `policy_sha256` and `numerical_policy_v2.yaml` are unchanged. Offering `RRC-revision-v1` (WO-4, D-1)
    adds one `get_project.solve_policies` entry, which M07a's MR-7 clause requires a register entry to name.
  - Every existing document validates unchanged, and fixtures regenerate byte-identically.
  - No registered policy, record, bundle, certificate or replay moves (design note §5.11, G1).
- **C2. Support matrix:**
  - L21 is narrowed;
  - L-COL-9 is narrowed iff G5 finds a failing-first column case, else it stays with "under the registered policies";
  - L20 and L24 are unchanged;
  - `docs/recovery-edges.yaml` gains E3c.
- **C3. Behaviour:** a rescued result under `RRC-revision-v1` can depend on project history (which ancestor was
  verified). That is a change of method, recorded in `branch_provenance` and the bundle, never a change of problem.

## Acceptance evidence

- The design note's G1–G10, F1 and F2, in `evidence/RRC/<commit>/manifest.json`, `tested`.
- Frank's FQ1 answer.
- The `reviewer` pass.
- `review.numerical` and `review.process_model` are not set by this ADR.

## Register entries (drafts, unnumbered)

**R-RRC-1 — Edge 3 on a revision region continues the revision's changed operating values from the nearest verified
ancestor.**
- **Decision:** D1–D4.
- **Rejected:** specification rows on revision regions (an empty path), a tear-connection homotopy (level identity),
  split-fraction continuation (a `ZERO_FLOW` endpoint, splitter loops only), heuristic easy values, partial
  continuation, nearest-by-distance, arclength.
- **Watch for:**
  - a session building `p⁰` from the failed opening on a revision region;
  - continuing a subset of `D`;
  - selecting by a float metric;
  - running this under `homotopy` or `homotopy_or_sequential_restart`.

**R-RRC-2 — The action order is specification continuation, then revision continuation, then the restart, with count 1.**
- **Rejected:** the restart first; a ladder of two recoveries (FQ3).
- **Watch for:** a restart run after a *taken* revision continuation; a refusal recorded as `taken`.

**R-RRC-3 — Continuable differences are a registered allowlist of operating specifications; default deny.**
- **Rejected:** allowing discrete parameters (`stage_count`, `feed_stage`) and model constants (`nu`, `damkohler`,
  `T_ref`, `T_scale`, `coolant_cp`); allowing any difference that leaves `model_version` equal.
- **Watch for:** a new unit parameter becoming continuable without a register entry.

**R-RRC-4 — The source is recorded in `solve-path.json` and replays from the bundle alone.**
- **Rejected:** content-addressing the source outside the bundle; re-binding the ancestor on rerun.
- **Watch for:** a rerun that consults the store.

**R-RRC-5 — L21 is narrowed; L-COL-9 is narrowed only on a failing-first column case (G5); R-827 is superseded only
under the new value.**
- **Watch for:** L-COL-9 claimed lifted on forced-edge evidence alone.
