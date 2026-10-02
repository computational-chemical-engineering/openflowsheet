# T02 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Acyclic execution, safeguarded Anderson recycle, coupled sparse EO blocks, cross-unit specification promotion (plan §4.2 row T02) |
| Authority | `docs/derivations/T02-recycle-spec.md` (A00–A36, amended by the review 2026-09-24), ADR 0009 (Proposed; accepted when the manifest is `tested`) |
| Lead | Design lane specifies and reviews, build lane implements |
| Branch | `wp/T02`, from `main` at `fe0a4de` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — green at **1533** |
| CI | green from `ec916a8` on (A34's cross-platform comparison under the comparability window) |

## Where we are

**Implementation complete; review complete; every finding closed.** Increments A–E
(`e63ec55`…`76b245d`); Fable review `docs/reviews/T02-review.md` (`76a0437`: 4 must-fix,
8 should-fix, rulings Q1–Q4, amendments to ADR 0009 D3 / ADR 0007 D2.2 / spec, register R-026).
Fixes: M4 `ec916a8`, M1+M3 `4682451`, M2 (+NEST-1) `c73a9a1`, S1/S3/S5/S6 `5e560ce`,
S2/S4/S7/S8 `a24ca16`, N9 `797484c`. Manifest generator `scripts/t02_evidence_manifest.py`
(`bd5d619`), being updated to post-review HEAD by its author (worktree branch `wp/T02-manifest`).

## Next action

**Closed.** Manifest `evidence/T02/b68585f775cc2b009ae1b130eebb865150cf943c/manifest.json` `tested` (37/37); ADR 0009 accepted; merged to `main`. Next
work: the v0.1 schedule review (plan §4.2), then T03.

## Open, recorded, not blocking

- `role: free` without a value is silently not freed (review N9) — handed to T03.
- Single-loop assumptions (N8), compile-per-step cost (N10) — revisit at the first multi-loop /
  large flowsheet.
- FOR FRANK (spec §13), defaults applied: F1 the duty-to-duty A02 instance discharges the plan's
  A02 test; F2 the liquid-guess cases are expected failures handed to T03.

## Anchors

`orchestrator/execution.py` (plan, `_tear_of`, `specification_regions`), `orchestrator/executor.py`
(plan run, M3 guard, region budget), `orchestrator/region.py` (§6), `numerics/anderson.py` (§5),
`orchestrator/merge.py` (§4.4), `run/compare.py` (`COMPARABILITY_WINDOW`), `scripts/t02_identity.py`.
