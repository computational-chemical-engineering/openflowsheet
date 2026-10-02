# T07 — campaign state

This is the current position, not the history. It is rewritten in place. Read it after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Plan §4.3 row T07: the job lifecycle and small HTTP/MCP bindings over the local application contract. Acceptance: ten agent tasks, ≥80% completion, zero unauthorized changes and zero false verification, plus duplicate-job, cancellation, injection and revision tests (gate V17; requirement D15) |
| Lead | Build / Design. The session led. Design lane: `architect` (design and rulings 1, 2, 4, 5b, 6, 7), `specifier` (V17 tasks, rulings 3, 5, R6, ADR 0002 A1), `reviewer` (two reviews), `verdict` (G17/V17) |
| Branch | `wp/T07`, merged to `main` 2026-09-28 |

## Where we are

**Done.** Evidence manifest: `evidence/T07/<commit>/manifest.json`, status `tested`.
- **ADRs:** 0019 (with A1 and A2) and 0020 are Accepted; ADR 0002 A1 and ADR 0013 A2 are applied.
- **Register:** R-091…R-116.
- **V17:** MET on `v17-c2` at 25/30. The first campaign, `v17-c1`, failed at 19/30 and that record stands. The verdict and its limitations are in `docs/reviews/T07-verdicts.md`.
- **Identity:** minus-`t07` is `9a7b4e6d…`. The `t07` key is recorded in the manifest.

## Handed on

- **Frank:** `review` sign-off of the package (numerical, process-model). His human review of the 17 MCP
  tool descriptions is recorded (2026-09-29, `REVIEW.json`, against the exact hashes); the design-lane
  text review of the descriptions is still pending.
- **Specifier:** R-088 Q24/Q25 as a K04 amendment; S-R5 (the name for tighten-only policies); S-G (GUESS roles on the revision binder); R4-O1 (Unicode noncharacters); R4-O2 (the verifier's own failed property call).
- **T08:**
  - F6 (outcome fallback revision_eo → legacy_eo, not built);
  - V17 generality: one pinned model; MCP-only agent evidence; T09 0/6; INJ-4 never exposed;
  - the run records lack the lock hash §7.6 wants;
  - review-2 N notes: a rank error class in `orchestrator/rank.py` has no typed end;
  - W4b limits: a region's events are lost on interrupt; verify has no cooperative checkpoint; the CasADi callback latent path.
- **Known limitation:** `worker.log` is readable through `get_artifact` (W6e-Q2, kept).

## Next action

None in T07. Next package: T08, per `docs/progress.md`.

## Standing directives

Frank: fewest limitations; robustness with recorded fallbacks; a fallback may change the method, never the problem. Decisions: `docs/T07_DECISIONS.md`.
