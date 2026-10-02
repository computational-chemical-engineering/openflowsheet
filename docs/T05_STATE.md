# T05 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | The v0.1 unit-model families: PH flash, conversion reactor, component separator, valve, liquid pump, two-stream exchanger (plan §4.3 row T05; gate V12) |
| Lead | Build / Design — `specifier` specified; the session implemented; `reviewer` reviewed |
| Branch | `wp/T05`, merged to `main` 2026-09-25 |
| Gate | green at 2548 (1915 before T05) |

## Where we are

**Done and merged.** Evidence `evidence/T05/91ac0103c1040175560d74d9afa2a091a8d25b2d/manifest.json`,
`status: tested`, 31/31 (A00–A30); CI run 36085409305 (x86-64, aarch64). ADR 0011 accepted; ADR 0004
D3.3 amended. `review` pending (Frank's sign-off; not claimable by an agent).

- Spec `docs/derivations/T05-unit-models-spec.md` (as amended by the ruling round); design note
  `docs/design/T05-generalization.md`; review `docs/reviews/T05-review.md`; rulings
  `docs/briefs/T05-rulings.md` §4; numbers `docs/t05-measurements.md`; build-lane decisions
  `docs/T05_DECISIONS.md`; register R-036…R-051.
- Identity after T05: `structural_sha256` `4ce030ca…` (unchanged); K05 identity document `622463f5…`
  (minus `t05`: `b364bb3d…`, the pre-T05 value); `check_policy_sha256` `21c44e10…`.

## Handed on

- **Registered v0.1 limitations:** near-pure PH feeds (§4.4, A29); a dormant PH-type outlet on the EO
  path converges at x⁰ and is `UNVERIFIED` (§4.7 (a), A28); a single flowing component in the latent
  jump on the EO path fails typed (§4.7 (b), A30). Remedies: a conditioning criterion (Q11); an ADR
  0005 regime-lattice change (Q12, and R-050's `ZERO_FLOW` fingerprint).
- **Scope:** `run_session`, bundles and the CLI stay SYN-001-only (design Q-G) — K06/T07 generalize;
  revision identity by label, no `compiled-problem-structure-v2` (Q-D, R-047).
- **Code notes (no defect):** the lifted-inlet enthalpy exists in three copies (`TPFlash._inlet_enthalpy`,
  `tp_state.stream_enthalpy_terms`, the separator's) — review N1; `tests/` is outside mypy and
  `tests/t05_trial_states.py` has cosmetic mypy errors.
- **T06:** C3 is a NET-07 candidate (T06 decides); T04 F9 (K04 fresh-flash tolerances) still open
  before T06 certifies EO solves in bulk — F9's mechanism was not active on C1–C3.

## Open decisions (defaults in force; for Frank, non-blocking)

Spec Q1 (`syn001.*` ids, family `SYN-001-UL`), Q2, Q3, Q7, Q8, Q9, **Q11, Q12**; design Q-D, Q-G.

## Next action

**T05b opened (2026-09-25)** on `wp/T05b`: Frank answered Q11 and Q12 — remove both limitations; the
dormant PH-type outlet (§4.7 (a)) is in scope too (build-lane DECISION, `docs/T05_DECISIONS.md`).
`specifier` is writing ADR 0012, `docs/derivations/T05b-limitations-spec.md`, the twin extension and
a work order from `docs/briefs/T05b-limitations.md`. Then: implement, reviewer, CI, manifest
`evidence/T05b/…`, merge. T06 waits behind this and the K04 F9 follow-up.
