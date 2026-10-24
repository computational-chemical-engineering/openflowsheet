# S10 build decisions

Build-lane choices the specification (`docs/derivations/S10-spec.md`, ADR 0047) left to the engineer. One line
each; each is isolated and revertible. Measurements go in the run log below.

## WO-S10-1 (spec §5.1-§5.3, §7.5 A01-A11, A23, A24-A28)

- DECISION B-1: what `flash()` does before WO-S10-2 → refused `unsupported`, message `flash_not_implemented: …`, no outlets, while `describe().flashes` already says `("TP",)` (A01 requires §5.2's value). Alternative: omit `flash` (breaks `isinstance(…, PropertyProvider)`) or declare `flashes=()` until WO-2 (fails A01). Reversible by: WO-S10-2 replaces the method and its test `test_the_flash_is_refused_until_wo_s10_2` (`647ce9a9`).
- DECISION B-2: loader cases §5.1 does not name → a parameter value that is not a finite number is `record_structure`; a Λ entry naming an unknown component is `record_lambda`; a P domain with lower bound ≤ 0 is `record_domain` (ln P); component keys required = ComponentRecord's required keys + `synthetic`, allowed = ComponentRecord's properties; Λ entry keys `i, j, value` (+ `provenance`). Alternative: no check (a crash or `math domain error` later). Reversible by: editing `_parameter`, `_lambda`, `_bounds` in `thermo/wilson_ig.py` (`647ce9a9`).
- DECISION B-3: where the U02 library-only text lives before S10 has a manifest generator → `U02_LIBRARY_ONLY` in `tests/test_s10_provider.py`, with a test that it and every harvested S10 U02 note name `` `wilson-ig-v1` `` and library-only. Alternative: a stub `scripts/s10_evidence_manifest.py` now. Reversible by: the manifest generator takes the string over and the test reads it from there, as S07's does (`9211297d`).
- DECISION B-4: ∂ln φ_i^L/∂n_j → the general projection (G_ij − Σ_k x_k G_ik)/n_tot of spec §3.6, not the shortcut (G_ij + 1)/n_tot (equal by ID-ROW). Alternative: the shortcut. Reversible by: one line in `evaluate_phase` (`647ce9a9`).
- DECISION B-5: `implementation_sha256` → hashed once per instance in `__init__`, no module-level `@cache`, so the T07 global-state allowlist is unchanged and the provider holds no process state. Alternative: `@cache` + allowlist entry (the `pr-c1-v1` pattern). Reversible by: moving the hash to a cached module function (`647ce9a9`).
- DECISION B-6: the S10 family's shape in `benchmarks/registry.yaml` → SYN-001-T06's keys plus `provider`, `status`, `records_sha256`, `cases_directory: null` with a reason, `budgets: null` with a reason; no cases (library-only). Alternative: no family until S10-C. Reversible by: deleting the family and its test (`77aaf55f`).
- DECISION B-7: θ₀ → the literal `0.29815` (spec §2), not `298.15 / 1000.0`. Alternative: the quotient. Reversible by: one constant (`647ce9a9`).

## Run log

- 2026-10-25, WO-S10-1. `tests/test_s10_provider.py`: 88 passed. Per group: A01 2, A02 21 (19 malformed copies covering
  all five codes, bitwise handover, code coverage), A03 1, A04 12, A05 12, A04/A05 worst 1, A06 1 (102 zeros), A07 1,
  A08 12, A10 12, A11 2, A23 2, A24 1, A25 1 (113 claims, 11.6 s), A26 1, A27 3, A28 1, type and flash refusal 2.
- Worst agreement over A04/A05 (every non-identity entry, E1-E6, both phases): 0.069 of the tolerance, at
  E4.LIQUID ∂h/∂n_VB: 6.9 × 10⁻¹⁴ relative, the spec's measured floor (FLOOR-E 6.93 × 10⁻¹⁴). E3's structural zeros
  come out exactly 0.0.
- Mutations re-run on the implementation (ratio of the worst entry to its tolerance): M09 unprojected 2.8 × 10¹⁴,
  M01 Λ transposed 1.9 × 10¹², M14 R = 8.314 1.9 × 10⁸ (the spec's 1.9 × 10⁸), θ₀ = 0 2.0 × 10¹².
- Registry and provider-registry tests (T08 envelope, unsupported, inventory; T07 global state; requirements ledger;
  S05/S07 registration; registry readers; document hashes): 590 passed, 11 skipped, 6 failed = T08's C3 harvest
  check only (`wilson-ig-v1: S10 has no U02 item in the harvest`), expected until S10's manifest is harvested, as for
  S05 and S07. ruff, ruff format and mypy clean on the touched files.

## Where WO-S10-1 stopped

Complete. Next: WO-S10-2 (`flash`, `stability()`, the message grammar; `tests/test_s10_flash.py` for A12-A22 and the
flash half of A23), then the `reviewer` pass on WO-1 and WO-2.
