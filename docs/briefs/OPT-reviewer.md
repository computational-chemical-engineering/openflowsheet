# Reviewer brief: OPT — the NLP optimiser on revision flowsheets (0.4), the single review pass

Status: brief, 2026-11-08. Design `docs/design/OPT-revision-optimisation.md` (architect `e4316d9c`; amended §9
`9318904a` after three premises failed by measurement) and ADR 0071 (Proposed; ADR 0019 Am. 16). Branch `wp/OPT`,
worktree `.claude/worktrees/opt`, head `48733e55`. Build log `docs/OPT_DECISIONS.md` (D-1…D-71, gate numbers per WO),
handoff `docs/OPT_HANDOFF.md`. Manifest `evidence/OPT/a46ea80f…/manifest.json` (`implemented`: OPT.D61 `fail` by
design; OPT.G21 and OPT.G13.aarch64 `unsupported`).

## The question

Does `wp/OPT` implement the amended design so that every reported optimum is judged on a certified re-solve (R-188),
existing identities are unchanged, and the new surface is sound — and what are the rulings on the batched D-items, so
the package can be closed?

## What was measured (engineers' numbers; re-run what you doubt, within the machine-load rule)

- Identity: F0 PASS M1–M9 after every WO; G2 SYN-001/E01 dumps identical to the pre-OPT base `ad971d32` in the default
  env (`6e028e8d…`) and the audited nlp env (`b6bbafdb…`, solved reports — earlier `--nlp` comparisons before WO-5c
  compared UNSUPPORTED reports, D-44, now re-taken); WO-2 G4: held system reproduces the converged attempt's residual
  bitwise on 8 cases.
- Analytic (mpmath, 30 digits): OPT-A1 Q rel 1.0e-11; OPT-A2/A2b all starts verified, ≤ 2.2e-10; OPT-N1 behaves as
  designed; OPT-A3 (bubble point) KKT verified on the phase-boundary form, |Q−Q*|/Q* 1.9e-11, λ rel 1.9e-11; OPT-A3v
  (dew point) G10d; G10a byte-identity anchor; G10c negatives. Cost/LCA: OPT-C0 rel 1.0e-11; G19 interior cost optimum
  vs golden section 0.23 Pa (tol 10 Pa), TAC vs hand rel 6e-16; G20 LCA vs bisection 2.6e-10 K, GWP bitwise to hand.
- C-MW (297 columns): both starts KKT verified after A-2/A-3 (zero subsystem 63/63, ethanol exactly 0.0 on re-solve).
- Surface: c_4 link (provisional; R-960 provisional), D_4 `3fb06cad…`, stripping gives D_3 `455d01eb…`; job, CLI,
  replay (re-checks the certified chain; committed fixture MATCHes without Ipopt on x86), cancellation G14, G12, G16.
- Not yet: full gate; CI aarch64 result for G13's fixture (the orchestrator is reading it).

## Rule on each (engineer's default in brackets where one exists)

1. The amendment's mechanisms as built: A-1 phase-boundary form (`studies/nlp/boundary.py`; D-45 Q1′ accepts the
   boundary basis; D-48 rebuilds the certificate target importing private `_staged_splits`; D-49), A-2 zero subsystem
   (D-39, D-41 side effect on TH-R1), A-3 guarded/unguarded margins (D-40, D-43; the "unguarded" admission rests on
   R-924 — the architect asked you to look at it).
2. D-12 → superseded by A-3? D-42 (γ–φ held single-phase splits never certify under K04's witness; queued as a separate
   design item with X10's L-X10-1) — confirm it is correctly a declared limitation here.
3. D-18 (assessment checks judged at the first certified start), D-24 (`starts: [[]]`), D-28 (two codes as reason
   details), D-30 (dropped flat `candidate_revision_sha256`, `$ref` revision), D-32, D-36/D-38, D-46 (unaudited stack
   refusal placement).
4. Surface: D-58 (Q26 allow-lists the request's numeric problem-definition containers by full path, as R-235) [accept],
   D-59, D-60 (schema resolver writes a `$comment` on a `$defs` self-reference), D-63 (G12 masks every wall-clock
   member), D-66 (a cancelled job keeps start 0's bundles only), D-67, the 588 KB committed replay fixture.
5. D-61: the two changed binding descriptions (`validate.md`, `submit_job.md`): **do the design-lane description review
   of their exact served text** (record your verdict in the review; the orchestrator records it in `REVIEW.json` with
   your name only if you pass them; the human review stays Frank's).
6. D-50 (G10d's two tolerances disagree), D-62/D-68 (replay's near-threshold rule), D-70 (Ipopt crawls to max_iter on
   OPT-L from the feasible side; start moved to 650 K; L-OPT-2) [declared limitation].
7. The architect's open facts: F2 (duty-spec margin vs `orchestrator/region.py` closure admissibility — now A-3), F3
   (Ipopt inline vs spawned worker identity, G12 passed with masks), and whether any certificate of an ordinary `solve`
   changed (it must not).
8. Is `implemented` right, and what must change for `tested` once D-61's reviews are recorded and CI is green?

## Least sure of

The boundary form's soundness (A-1: is removing exactly the active splits' directions the right regularity judgement,
and can it ever pass a point that is genuinely singular for another reason?); replay's float comparison of near-zero
KKT members across architectures (no registered floors; D-62); the unguarded admission.

## Deliverable

`docs/reviews/OPT-review.md`: verdict, must-fix (M*), should-fix (S*), one ruling per item, the D-61 design-lane
description verdicts, amendment text where a ruling needs one, what the review did not establish. Commit on **main**
(docs-only, named path, message `docs: OPT review`, with the session's Co-Authored-By / Claude-Session lines). Do not
edit `wp/OPT`. Never set `reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; targeted tests only, one at a time, `OMP_NUM_THREADS=1`; no full gate.

## Out of scope

RRC, X02, MSG, ST; K04's witness policy (separate item); X12, X24; style.
