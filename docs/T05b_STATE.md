# T05b — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Remove T05's PH/EO limitations and close T04 F9 (Frank, 2026-09-25: fewest limitations; robustness with recorded fallbacks) |
| Lead | design lane specified (`specifier`), reviewed (`reviewer`); the session implemented |
| Branch | `wp/T05b`, merged to `main` 2026-09-25 |
| Gate | green at 3141 (2548 before T05b) |

## Where we are

**Done and merged.** Evidence `evidence/T05b/ba9a27b422834138daeff98481072c65db8b3744/manifest.json`,
`status: tested`, 64/64 (B00–B36, X00–X26); CI run 36169942463. ADRs 0012 and 0013 accepted;
`review` pending (Frank's sign-off). Specs `docs/derivations/T05b-limitations-spec.md`,
`docs/derivations/K04-F9-spec.md`; reviews `docs/reviews/T05b-review.md`; rulings
`docs/briefs/T05b-rulings.md`; numbers `docs/t05b-measurements.md`; decisions `docs/T05_DECISIONS.md`.
Identity: SYN-001 minus `t05`/`t05b` `b364bb3d…`; `t05` `ddbd0f71…`; `t05b` `4f29500e…`; structural
`4ce030ca…`; check policy `21c44e10…` (unchanged).

## Handed on

- **Registered limitation:** zero-duty flash fed exactly at its dew point — provably singular declared
  form, `UNVERIFIED` (§18 Q9); six B34 sweep runs near it certified `FAILED`, `false_success_detected`.
  Default: a K04 follow-up (certifying a singular-but-correct root).
- **Design-lane follow-up:** `onenormest` makes `rcond_1`/`inverse_one_norm_estimate`/the bound depend
  on numpy's global RNG (C2 bound 3.0e-15…3.9e-15, C3 3.0e-9…3.4e-9 over 20 seeds); no R0 field moves.
- **Build-lane notes:** `augment` recursion (make iterative before large flowsheets); the verifier's
  degeneracy test has no pre-screen (cost, T06); `scripts/t05_evidence_manifest.py` fails A23 at later
  heads by design (T05's evidence stays at `91ac010`).
- **Schema:** `evidence-manifest` `work_package` now allows one lower-case suffix (not frozen).

## Open decisions (defaults in force; for Frank, non-blocking)

T05b §18 Q9; K04-F9 §12 Q1 (F10 checks in SYN-001's legacy set, would move SYN-001's identity);
T05 Q2/Q3/Q7/Q8/Q9.

## Next action

None in T05b. Next package: T06, per `docs/progress.md`.
