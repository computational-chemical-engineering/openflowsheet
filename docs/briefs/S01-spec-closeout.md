# S01 — specification close-out (design lane, `specifier`, small pass)

Branch `wp/S01` in worktree `/home/user/ofs-s01`. Predecessor handoff: `docs/briefs/S01-handoff.md` (gaps 1–2 are
this pass; gaps 3–5 go to WO-2/WO-3 by design and are out of scope).

## The question
Close two gaps so every registered expectation in `docs/derivations/S01-spec.md` is generator-derived.

## Facts with anchors
- Spec A19 row: `docs/derivations/S01-spec.md:216` (partial-dormancy probe); its WO: `:242-244`; non-claim `:261`;
  decision `:282`. Dormant cases D1/D2: `:173-174`; A13/A14: `:210-211`.
- Generator `docs/derivations/scripts/s01_reference.py` (mpmath 50 digits; `claim()` :56; `inlet()` :93;
  `solve_case` :418; `dormant_section` :609 — static values today; `build` :669; `main` :704) and its output
  `docs/derivations/scripts/s01_reference.json`; `--check` passes 127 claims today.
- Gap 1: register A19's side feed in the generator: `(0.2, 0.5, 0.3)` mol/s, 340 K, `P_r`, liquid, stage 3, N = 3,
  Q = 0; its root is analytic (stage 3 a liquid pass-through, `T_3 = 340` K, stages 1–2 `ZERO_FLOW`) — derive and
  claim it (or, if that root fails §8's acceptance, say so and register what A19 expects instead).
- Gap 2: `dormant_section` writes D1/D2 as static values. Derive the label chain (§4.6 closed form, `T_j = 330` K,
  `ZERO_FLOW` ×3; D2's `SPECIFICATION_CONFLICT` cause) by claims, not literals.

## Exit test
`/home/user/openflowsheet/.venv/bin/python docs/derivations/scripts/s01_reference.py --check` passes with the new
claims (state the new count); spec rows A13/A14/A19 cite the generator's JSON keys; ruff check/format clean; the
handoff file updated (gaps 1–2 closed). Commit on `wp/S01` (`S01:` prefix, the two trailer lines).

## Out of scope
Gaps 3–5; any other spec change; code under `src/`.

## Agent rules
Context cap ~60k for this pass; report ≤ 100 words. DECISION lines to `docs/S01_DECISIONS.md`.
