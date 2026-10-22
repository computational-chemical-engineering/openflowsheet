# S05 (IAPWS-95) — independent review and ruling round (design lane, `reviewer`)

Branch `wp/C10` (worktree `/home/user/ofs-c10`). The package's single `reviewer` pass; it carries the open questions.
S05 adds a property provider (residuals, derivatives, phase logic, saturation, caches).

## The question
1. Do WO-S05-1 (`src/openflowsheet/thermo/iapws95.py`, `benchmarks/s05/iapws95_coefficients.json`,
   `tests/test_s05_iapws95.py`) and WO-S05-2 (`tests/test_s05_envelope.py`, `scripts/s05_mutations.py`,
   `scripts/s05_evidence_manifest.py`, harvest rows) meet `docs/derivations/S05-IAPWS95-spec.md` and ADR 0045, and do
   the tests verify what A01–A30 claim (mutation-minded)? Independence of `docs/derivations/scripts/s05_reference.py`
   and `s05_crosscheck.py` from `src/`; residual/derivative consistency; exact-input caches; refusals.
2. Rule on the open `QUESTION:` lines in `docs/C10_DECISIONS.md`: the Newton convergence rule (step stops shrinking
   below √ε); spec §3.1/§3.5 amendments (p_σ from the vapour side; Z = P/(ρR_sT) at a solved root); A17 — 21 strict
   xfails (near-critical in T, four domain corners, band probes; is the registered stencil/tolerance right there, or the
   code? a tolerance changes only with a derivation that the registered value was wrong); A29 mutation m5 (not
   observable by A15 because p_σ lies inside the near-critical box — drop or restate); Q-5, Q-6 of the spec.
3. Rights: C10-Q1 stays Frank's (IAPWS terms unread from this session); state what the manifest must say about it.

## Facts
Manifest `evidence/S05/601e04f…/manifest.json` (`implemented`; 32/35; S05.gate unsupported); register R-585…R-594;
handoffs `docs/briefs/S05-WO1-handoff.md`, `S05-WO2-handoff.md` if present. Env: from the worktree,
`PYTHONPATH=$PWD/src /home/user/openflowsheet/.venv/bin/python -m pytest -q tests/test_s05_*.py`.

## Exit test
`docs/reviews/S05-review.md` (must-fix / should-fix / note with file:line and a failure scenario; rulings; the fix
work order), a dated amendment in the spec, register entries **R-595…R-599**. Do not edit production code; do not set
`reviewed`; do not run the whole suite. Report ≤ 150 words.
