# Brief — T08 review 2: the harvest classification, the recovery-edge inventory, and rulings on the envelope

**To:** `reviewer` (design lane). **From:** build lane, 2026-10-01. **Branch:** `wp/T08` at HEAD.
**Deliverable:** `docs/reviews/T08-review-2.md` with (A) findings on W2.2 and W2.4 ranked M/S/N (file:line,
failure scenario, smallest fix) and (B) a ruling on each question of §3, each with the decision, the rejected
alternative, and the **exact amended text** (for `docs/derivations/T08-release-spec.md`, or the YAML/inventory) so
the build lane can transcribe it as an amendment without deciding anything. Write no production code; do not
commit. Never set `reviewed`.

**Budget.** Frank is near his weekly usage limit; this is the one design-lane pass for Phase 2. Be decisive and short.

## 1. What to review

- **W2.2, the harvest (T08.A21, marked R in spec §15):** `990d0a2`. Release spec §5.7: every `limitations[]` entry and
  non-`pass` check of every manifest under `evidence/`, classified exactly once E (user-facing → an L-row) / S
  (superseded/closed → closing test or check) / P (provenance/process note) / B (v0.2 backlog). 18 manifests, 256
  items: E 90, S 41, P 123, B 2. Files: `benchmarks/t08/support_envelope.yaml` (find the harvest/classification
  section), `scripts/t08_support_matrix.py`, `tests/test_t08_w2_support_envelope.py`. **A misfiled E-as-P hides a
  limitation** — the P class is where to look. The engineer flagged: T03 L16, T05 L12, T05b L14 ("handed-on,
  unreachable"); K03 L0, P03 C17, T06 L12, T07 L3, T02 L15; S→document pointers K01 L8, K03 L7, P00 L7, T07 L2. Sample
  the rest.
- **W2.4, the recovery-edge inventory (T08.A33, marked R):** `35f4cee`, `docs/recovery-edges.yaml`,
  `tests/test_t08_w2_recovery_edges.py`. Release spec §5.6. Labels are read from code (Literal types + AST scan), the
  bijection holds (37 labels); A33 fails on purpose for E1, E5, E10, E11, E12 (no unchanged-physics evidence). Check
  the scan cannot miss a producer, the rows' `enabled` values, and the evidence pointers.
- Also landed in Phase 2a (no R mark, glance only if time): `9b62ca2`/`fbd07ed` envelope + `docs/support-matrix.md`
  (T08.A20, A22, A23), `b97125c` alias threshold (A24), `b19c7d7` ledger (A02).

## 2. Context you need

`docs/T08_DECISIONS.md` (entries "Phase 2a" and "W2.4 landed", 2026-09-29) lists the engineers' choices. Frank's
rulings so far: V14 (b) carried as FAIL into v0.1 (ADR 0021 D3 row); F5 V17 carried; warm starts built (V13 (e)
awaits its verdict). CLAUDE.md: no placeholder success paths; unimplemented capabilities return explicit unsupported
results; no relaxed checks.

## 3. Rule on these (each: decision, rejected alternative, exact text)

1. **U05.** §5.3 says `validate(task="optimization")` is a typed refusal; the code returns
   `READY_FOR_OPTIMIZATION` for a closed revision (`src/process_runtime/application/validation.py:293`, measured on
   SYN-001-nominal) although v0.1 has no optimizer. Amend U05, or a rule-5 defect for the build lane to fix (and how
   it must fail)?
2. **§5.2 components.** "any non-empty subset of {A, B, C}" (spec :186) vs `canonical_components`
   (`models/revision_flowsheet.py:228`, R-076, T06 A60): only a permutation of (A, B, C). Amend.
3. **L10** seed text "No warm starts across runs" is stale; the engineer restated it. Confirm or correct.
4. **Harvest rules** the build lane chose: an E item may point to a U-row; a compound item may carry several
   pointers; an S item may point to a document (ADR, LICENSE, REVIEW.json). New rows L18–L35 (L22 "solver evidence
   scope" is broad — split or prune?).
5. **Unchanged-physics evidence for E1, E5, E10, E11, E12.** New identity-comparing tests (engineer's
   recommendation: one per row, on a real model, not a synthetic map), or an accepted structural argument (these
   act inside one solver call or inside verification/validation)? If tests: say exactly what each must compare.
6. **Which kinds of evidence count:** direct identity comparison (T04 §5.4); a VERIFIED certificate (its guard,
   `verify/certificate.py` `_guard`, refuses a changed `model_version`, `constants_sha256` or revision); T03 A16's
   injected-identity guard. E3b, E6, E7, E8 rest on the certificate kind, E4 on the guard.
7. **E7:** `fallback:tp` has two producers; the failure-triggered one (PH closure gives no answer) has only a
   kernel-level test (KS-3) and no certified end-to-end run. Enough?
8. **E1/E2 `enabled: default`** although every v0.1 unit declares exact derivatives and `legacy_eo` plans one
   `solve_eo` step, so no application policy reaches them. `default`, `policy-only`, or "unreachable in v0.1"?
9. **E5 emits no trace label** (declared unlabeled). Acceptable for v0.1; backlog a label (an identity change)?
10. **E9** runs only through the warm-start path (K03 §10.1's chain on the SYN-001 tear path is not implemented,
    K03 manifest limitation); `initializer_rejected` is shared with terminal rejections and E3b's P4. Any consequence?
11. **CLI `replay --rerun` fallback.** For an unknown run id it re-runs SYN-001-nominal
    (`src/process_runtime/application/cli.py:183`; kept deliberately in T07, design note §12.3, §17 D-Q6; the
    application's `reproduce` does not copy it). It changes the problem being compared. Registered limitation, or
    a rule-5 defect to fix (typed refusal) before v0.1?
12. **Inventory location.** `docs/recovery-edges.yaml` (three registered literal guards forbid the refined-core,
    edge-3 and phase-contract literals in YAML under `benchmarks/` and `tests/fixtures/`), or `benchmarks/t08/` with
    an ADR'd guard exemption?
13. **T07 L3:** the design-lane text review of the 17 MCP tool descriptions is still `pending_design_review` in
    `src/process_runtime/application/bindings/descriptions/REVIEW.json` (Frank's human review is recorded). Must it
    be done before the v0.1 tag (and by whom), or is it a limitation?

## 4. Do not spend time on

PTC-R1 (judged; V14 (b) FAIL accepted), warm-start internals (reviewed in `docs/reviews/T08-review.md`), style,
Phases 3–5.
