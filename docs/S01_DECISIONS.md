# S01 — build decisions (countercurrent equilibrium-stage subsystem)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: S01 provider → SYN-001 only (PR C1 is vapour-only). Alternative: none without a new property method. Reversible by: adding a provider in a later package.
- DECISION: S01 form → a unit-layer cascade (rows, initializer, pre-solve) that calls `solve_region` unchanged. Alternative: its own attempt controller, or N stage units on the traversal path. Reversible by: S02 registering the stage rows as library units.
- DECISION: continuation easy endpoint → the isothermal pre-solve root `x⁰`, an exact root of ADR 0010 D2's `H(·,0)` with `p⁰ = Q(x⁰)`. Alternative: a K-value/CMO model homotopy (not a real flowsheet at λ < 1; needs an ADR). Reversible by: an ADR adding a model homotopy.
- DECISION: split feed → lift `m_j` (C extra columns and rows per stage, DOF-neutral). Alternative: widen `LiftedSplit.feed` to sums (moves its registered digest). Reversible by: an ADR widening `LiftedSplit`.
- DECISION: dormant-stage label → `T_{j−1}` (`T_top` for j = 1). Alternative: the vapour inlet's temperature. Reversible by: amending §4.3 (no registered identity uses it yet).
- DECISION: partial dormancy → not claimed; A19 asserts no false success. Alternative: a structural-dormancy opening rule. Reversible by: a later package adding the rule and an assertion.
- DECISION: inlets → declared single-phase only; two-phase is `unsupported`. Alternative: lifting an inlet split. Reversible by: adding the lifted inlet form.
- DECISION: β̄ clamp → [0.1, 0.9] and CMO floor 0.1·F. Alternative: unclamped (the pre-solve degenerates at β̄ ∈ {0, 1}). Reversible by: changing two constants and re-emitting `ref`.
- DECISION: inlet pressure vs stage pressure → no relation in S01 (enthalpy at the inlet's own state). Alternative: an equality row. Reversible by: S02's feed conventions.
- DECISION: ADR 0043 → not needed (no ADR or frozen interface changes). Alternative: an ADR for the pre-solve. Reversible by: writing it if review disagrees.
- DECISION: dormant inlets of D1, D2 and A19 → C2's `top`/`bottom` states with zero flow (330 K liquid, 380 K vapour, `P_r`). Alternative: equal inlet temperatures (a label taken from the wrong stream would then pass). Reversible by: changing `DORMANT_TOP`/`DORMANT_BOTTOM` and re-emitting `ref`.
- DECISION: A19 expectation → a §4.5 outcome other than a §5 refusal (the generator proves the probe valid), or a `CONVERGED` root passing §8; with signature (`ZERO_FLOW`, `ZERO_FLOW`, `LIQUID`) it must equal `ref.partial_dormancy.target`. Alternative: "no false success" alone. Reversible by: amending the A19 row; partial dormancy stays unclaimed (§14).
