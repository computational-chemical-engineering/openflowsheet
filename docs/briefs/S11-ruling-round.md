# S11 brief: the batched ruling round on the build lane's escalations (design lane, `specifier`)

Worktree `.claude/worktrees/s11` (branch `wp/S11`, head `645c1e22`: tracks A and C complete, B complete, D1/D4 merged; D2/D3
running on `wp/S11-d`). Design: `docs/derivations/S11-design.md` (ADR 0050; §9, §10 amendments) and
`docs/derivations/S11-units-design.md` (ADR 0051). Build logs (each item below is logged there with its evidence):
`docs/S11A_DECISIONS.md`, `docs/S11B_DECISIONS.md`, `docs/S11C_DECISIONS.md`, `docs/S11D_DECISIONS.md`.

## 1. The question

Rule on each item below — **accept**, **change** (exact text/code intent and acceptance test), or **revert** — so the
integration work orders (I1, I1b, D5, D6, I2) and the single final `reviewer` pass have nothing left to choose. Governing
rules: no relaxed checks, removed cases or narrowed denominators to pass a gate; a self-generated output is a regression
fixture, not validation; Frank's directive: as few limitations as possible. Register from **R-830** (check the tail of
`docs/decision-register.md` for the last id used; R-800…R-827 are S11's design passes).

## 2. Items that block the final gate or the release (rule first)

1. **T08.A32 vs the two new record files** (S11A, A1): `tests/test_t08_w2_inventory.py::test_a32_…` refuses
   `benchmarks/s05/components.yaml` and `benchmarks/s07/components.yaml`: not in `VETTED_RECORD_FILES`, no InChI, and the
   cross-convention identity rule fails against l01/m01/s10 (e.g. `Water` vs `water`). Left failing. Track A's proposed
   default: a registered exemption for files whose records only name a fluid the provider already defines. The full gate
   cannot pass until this is ruled.
2. **Wilson column certificates UNVERIFIED** (S11B, B4; blocks S11.A35 on C-MW/C-EW): 407 of 409 checks pass; the two
   derivative-witness checks are `unsupported` because the finite-difference step pushes an absent component's exactly-zero
   internal flow negative and the Wilson provider refuses that state. Only pr-c1's zero stream flows are exempt today (R-281).
   Track B's proposal: extend the exemption, with the `derivative_witness_partial` limitation. Certificate policy.
3. **W27 v3 Q-1** (S11A, A4; state W27v3-A08): the Wilson records have no CAS RN; v2's spelling rule (kept by v3) refuses
   them once a case spells them (measured spellings: CH3OH, H2O, ethanol, methanol, water), so v3 refuses the S11 build at
   classification — contradicting §4.10's "serves no case". Proposed default: the spelling rule skips records with no CAS RN.
   Must be decided before the release's W27 run.
4. **Kernel fix C3-1** (S11C): `models/thermal/kernel._solve` reset `previous` to ∞ after any bisection, against R-600 (∞ only
   after a non-positive slope); fixed in `36ea9175` (40×40 water grid: 7 outcomes `not_converged` → converged, residual ≤
   1e-12; 2 liquid states moved ≤ 3.1e-15 relative; rest bit-identical). New S11 code only. Confirm.

## 3. Assertion clauses that cannot hold as written (restate or revert)

5. **Q-C1 / C1-4** (S11C): A46 (Jacobian vs central differences, 1e-6) near water's critical point (~647 K): the provider's
   rounding floor means no admissible step reaches 1e-6; the engineer added the measured floor to the tolerance there,
   capped at 1e-4. **This is a tolerance change to pass a check** — rule whether A46 is restated (with what justification and
   bound) or the change reverted and the region excluded as a stated limitation. Also C1-3 (scaled comparison; tiny entries
   pinned by thermodynamic identities to 1e-9).
6. **A12** (S11A): "exact ==" material balance holds only for split products exact in binary64 (existing splitter leaves one
   ulp at n = 0.4); the Wilson case uses flows (0.25, 0.25, 0.5).
7. **A68 "square"** and **A77(iii)** (S11D): A68 read as "same rows and variables as the SYN-001 flowsheet of the same shape"
   (K02's pressure rows restate a feed pressure, so neither is square by count); A77(iii) tests only the 8 of 18 (component, T)
   pairs whose P_sat is inside the records' pressure domain, the other 10 checked refused `out_of_domain`.
8. **§4.10 "all existing W27 tests pass unchanged"** (S11A): impossible after A1 (D9); A1 reads the installed build under v1/v2
   through `v2_binder()` (`7302a507`); one W27 test (`test_c9_w27_v2` version switch) now uses version 4 instead of 3.

## 4. Build decisions for confirmation (each isolated and revertible)

9. **S11B:** B3c — no `s11-column-v1` policy (Q8's premise wrong: `T06-revision-v2` already carries phase contract v2 and
   solves the column; a new policy would change the served `solve_policies` list two tests pin). B3b — R-824 makes S02's
   "wrong kind for this end"/"kind not offered" refusals unreachable from a document (now `parameter_unsupported`); no
   optional-parameter field in `ModelSignature`. A91 — the reader already refuses ids with a dot, so A89's collision is tested
   with key `U-BOT`. B4 — specification checks in the table's linear form with the policy's tolerances (no dimensionless
   tolerance kind for the quotient form); stage checks evaluate the standalone column equations at the judged state; a column
   stage with V = L = 0 and a dormant feed raises `zero_flow_form_unknown(syn001.column)` (per-stage zero-flow form not
   importable by `verify/zero_flow.py`).
10. **S11C:** Q-C2 — the turbine's `isentropic_phase` cannot be stated in a revision (numbers only); default: always the
    outlet's form, a parameter of that name refused `parameter_unsupported`. O-C4-1 — R4 (one phase per port) means a revision
    mixer cannot take a liquid and a vapour inlet; A56's mixed-inlet case stays direct construction. C3-2 — β_s outside [0,1]
    reuses `isentropic_state_two_phase`. C4-2 — thermal builders skip `instance_contract` (its R4 check would refuse every
    `vapor_liquid` outlet). C6-2 — `test_m02_wo8_registries` restricted to keys outside `thermal.` (not in §8.3). C6-3 — A63's
    hint asserted on the valve's own answer (the plan keeps the message's first line only). O-C6-1 — under v1 the A62 Q = 1 kW
    case gives `LINEAR_SOLVE_FAILED`; §4.9's `RANK_DEFICIENT` is a certificate status, checkable after I1b. O-C3-1 — 4
    supercritical h closures near the pseudo-critical line return `not_converged` (provider phase label jumps at T_c).
11. **S11D:** v2 result `provider_id` = `wilson-ig-v2` (orchestrator decision; values bitwise v1). `ph_kernel` failure labels
    use SYN-001's reference convention on Wilson (label only, file outside D1's list).
12. **S11A:** CoolProp records `elemental_verification: NOT_APPLICABLE`; routing-model hints on C1 name only SYN-001 and C1;
    routing `evaluate()` reports the bound convention; A17 tested directly on `revision_checks`; L01 measurement binding keeps
    only the bases W27 v2 has lines for.
13. **Identity gate (S11A, WO-0 decision 4):** family C ignores `revision_id`/`parent_revision` (clock-named in three
    `test_t07_r6_replays` tests); `revision_sha256` counts only as "equals the hash of the document as passed in".

## 5. Deliverable

`docs/reviews/S11-rulings.md`: per item, the ruling and reasoning (≤ 8 lines each), exact replacement text for any assertion,
and a work order line (which WO — I1, I1b, D5, D6 or I2 — carries it, with its acceptance test). Register entries from R-830.
Dated errata lines in the two design notes where an assertion changes. A docs-only commit on `wp/S11` including this brief.
Do not edit code; do not push. Report in at most 20 lines.
