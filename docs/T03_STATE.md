# T03 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | General procedural-phase active-set controller and checkpoint compatibility (plan §4.3 row T03) |
| Acceptance (plan) | No signature change during attempt; trial rejection/restart; sparsity rebuild; disappearing/reappearing phase; bounded cycling; multiple-root provenance |
| Lead | Design / Build — `specifier` specified, the session implements, `reviewer` reviewed |
| Branch | `wp/T03`, from `main` at `128b54b` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — green at **1611** at `6ac24be` |

## Where we are

**Specification** `c799ad9` (A00–A26, ADR 0005, R-028). **Implementation** W0–W11 complete
(PHS-01…05 and PHS-SYN-1/2 reproduce the 40-digit twin trial by trial).

**Review** `docs/reviews/T03-review.md` (`7c4bddb`, §8 ruling `c1c3288`): 3 must-fix, 5 should-fix,
all fixed —
M1/M2/S3 `4a2dd2c`; M3 + A21 `verify()` refusal `b51cab2`; S1 `54abc11`; S2 `b5d6bf5`; S4/S5
`796182b`; notes N3/N4/N6 `0b90ea9`, N7 `e2ae4a5`, N2 `65ac2d1`. Not addressed (notes, "no change
required"): N1, N5, N8–N11.

**Manifest** `evidence/T03/6ac24be9da572a90b198ba91b81d603f082cfa74/manifest.json`: `status: tested`,
27/27 (A23 on CI run 36019081919). ADR 0005 **Accepted**. **Merged to `main`** 2026-09-24. Campaign
closed; what outlives it is below and in `docs/progress.md`.

## Open decisions (defaults taken; flagged for the design lane)

- **M3 scope.** Provider calls made *inside* the compiled problem by its property blocks carry the
  context bound at assembly (K01/K02: one compiled problem serves every attempt), field-equal to the
  attempt's — not the attempt's object as the review's literal correction asked. Test asserts three
  categories (compiled calls: attempt's object; tear calls: attempt's object; block calls:
  field-equal). Routing the object into CasADi callbacks = compiled-boundary change. In manifest
  limitations.
- **S1 tear-path twin not folded in.** `solve_tear` still returns `attempts=0`, `x=start` on a budget
  refusal (K03's registered capped-budget shape). Handed to T04/K05 (review §7 allows).
- **K04 defect handed on** (review §8): `CONVERGED` without `x_final` → schema-invalid certificate.

## Next action

None in T03. Next package: T04 (brief to `specifier`), which inherits PHS-05 / the 377 K guess
(spec F1) and S1's tear-path budget shape.

## Parallel track

T06 references on `wp/T06-refs` (pushed, not merged; worktree `agent-a6b911745d46ad3fe` kept with
envs). For Frank (non-blocking): IDAES HSL licence disclosure; .NET 8 EOL 2026-11-10; PHS-05 to T04
(F1); registry class `phase-controller case` (Q3).
