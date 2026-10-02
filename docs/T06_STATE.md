# T06 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Plan §4.3 row T06: rank/conditioning and verifier; 30+ distinct cases; robustness generators; eight reference comparisons (gates V16, V18, V20) |
| Lead | Design / Build — `specifier`, `architect`, `reviewer`, `verdict`; the session implemented |
| Branch | `wp/T06`, merged to `main` 2026-09-27 |
| Gate | green at 4245 (3141 before T06) |

## Where we are

**Done and merged.** Evidence `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json`,
`tested` (100: 96 pass, 4 not_applicable). ADRs 0014–0018 accepted; `review` pending (Frank).
Spec `docs/derivations/T06-corpus-spec.md` (+ Amendments 1–5), twin 347 claims (`e97f61ce…`), register
R-066…R-089. Scoring: run 1 FAIL (stands), run 2 PASS on both architectures, run 2r and the holdout
(436/440) committed under `benchmarks/t06/ensemble/runs/`. References 16/16 AGREE. Identity after T06:
structural `915c97e8…`; K05 document `9a7b4e6d…` (`t06` key `e0e871f6…`).

## Handed on

- **T07 questions** (R-088; spec Q24–Q29): closure at `x_final` when the projection is refused is
  stricter than the rows (FAILED vs UNVERIFIED); the W2 pressure shift by position makes certificates
  UNVERIFIED from ~20 streams; W14's refusal cannot fire on the production path; W3 seeding not
  thread-safe; refinement message floats vs R0; NaN / integers > 2⁵³ in unread fields crash
  canonicalization; the legacy binding accepts `True`/`"300"` and raises untyped on `"abc"`;
  `validate()` cannot read revision flowsheets (F5); K05 bundles for revision flowsheets (Q6).
- **T07 defaults (Frank):** `newton_refined` and the F4 sequential restart are the application defaults.
- **Not run:** the §6.7 stress profiles (reported-only by design). W21's `lnK` memo (cost) left with the
  design lane. Registered limitation: a zero-duty flash fed exactly at its dew point is `UNVERIFIED`
  (T05b §18 Q9).
- **T08:** OpenIDAES-450 (other session, `study/openidaes450`) as candidate real-chemistry references.

## On merge (done)

Notify session **process-simulator-75** that `wp/T06` has merged; it then does ADR 0008 Amendment 1's
W4 register bookkeeping (R-001 text, §A1.8) on `adr/transient-readiness-2`.

## Next action

None in T06. Next package: T07, per `docs/progress.md`.
